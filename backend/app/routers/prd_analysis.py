from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import AsyncGenerator
import json
from app.database.connection import get_db
from app.core.security import verify_token
from app.services.prd_review_agent import analyze_prd_with_streaming
from app.crud.prd import get_prd
from app.crud.notion import get_page_by_id
from app.crud import user as user_crud

router = APIRouter(prefix="/prd-analysis", tags=["prd-analysis"])

async def stream_prd_analysis(
    prd_content: str, 
    prd_title: str, 
    prd_type: str, 
    db: Session,
    current_user = None  # Add current_user parameter
) -> AsyncGenerator[str, None]:
    """Stream PRD analysis events as Server-Sent Events."""
    
    try:
        yield f"data: {json.dumps({'type': 'status', 'message': f'Starting analysis of {prd_type} PRD: {prd_title}'})}\n\n"
        
        current_section = None
        sections_completed = 0
        total_sections = 5  # We now have 5 sections
        
        async for chunk in analyze_prd_with_streaming(prd_content, prd_title, db, current_user):  # Pass current_user
            # Handle different types of graph updates
            for node_name, data in chunk.items():
                
                # Track section analysis progress
                if node_name == "generate_report_plan":
                    sections = data.get("sections", [])
                    total_sections = len(sections)
                    yield f"data: {json.dumps({'type': 'log', 'message': f'Generated analysis plan with {total_sections} sections'})}\n\n"
                
                elif node_name == "analyze_section":
                    # This is parallel execution - each section completion
                    completed_sections = data.get("completed_sections", [])
                    retrieval_logs = data.get("retrieval_logs", [])
                    
                    # Stream retrieval logs first
                    for log_msg in retrieval_logs:
                        yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                    
                    if completed_sections:
                        for section in completed_sections:
                            sections_completed += 1
                            
                            # Send log update only (no individual section data)
                            yield f"data: {json.dumps({'type': 'log', 'message': f'Completed analysis for {section.name} section ({sections_completed}/{total_sections})'})}\n\n"
                
                elif node_name == "compile_final_report":
                    final_report = data.get("final_report", "")
                    if final_report:
                        yield f"data: {json.dumps({'type': 'final_report', 'content': final_report})}\n\n"
                
                # Log other main graph node executions
                elif node_name in ["generate_report_plan", "compile_final_report"]:
                    if node_name == "generate_report_plan":
                        yield f"data: {json.dumps({'type': 'log', 'message': 'Planning analysis sections...'})}\n\n"
                    elif node_name == "compile_final_report":
                        yield f"data: {json.dumps({'type': 'log', 'message': 'Compiling final analysis report...'})}\n\n"
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'Analysis completed successfully!'})}\n\n"
        
    except Exception as e:
        error_msg = f"Analysis failed: {str(e)}"
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"

@router.get("/analyze/{prd_id}")
async def analyze_prd_stream(
    prd_id: str,  # Format: "user-123" or "notion-456"
    token: str = Query(..., description="Authentication token"),
    db: Session = Depends(get_db)
):
    """Stream PRD analysis for a specific PRD."""
    
    # Verify token manually (since EventSource can't send custom headers)
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid authentication token"
    )
    
    try:
        # Get email from token
        email = verify_token(token, credentials_exception)
        # Get user object from email
        current_user = user_crud.get_user_by_email(db, email=email)
        if current_user is None:
            raise credentials_exception
    except HTTPException:
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': 'Invalid authentication token'})}\n\n"]),
            media_type="text/event-stream"
        )
    except Exception as e:
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': f'Authentication error: {str(e)}'})}\n\n"]),
            media_type="text/event-stream"
        )
    
    # Parse PRD ID and get content
    try:
        if prd_id.startswith("user-"):
            # User-created PRD
            prd_db_id = int(prd_id.replace("user-", ""))
            prd = get_prd(db, prd_db_id, current_user.id)
            if not prd:
                raise HTTPException(status_code=404, detail="PRD not found")
            
            prd_content = prd.content or ""
            prd_title = prd.title
            prd_type = "user"
            
        elif prd_id.startswith("notion-"):
            # Notion PRD
            notion_id = int(prd_id.replace("notion-", ""))
            notion_page = get_page_by_id(db, notion_id, current_user.id)
            if not notion_page:
                raise HTTPException(status_code=404, detail="Notion PRD not found")
            
            prd_content = notion_page.content or ""
            prd_title = notion_page.title
            prd_type = "notion"
            
        else:
            raise HTTPException(status_code=400, detail="Invalid PRD ID format")
        
        if not prd_content.strip():
            raise HTTPException(status_code=400, detail="PRD content is empty")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid PRD ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving PRD: {str(e)}")
    
    # Return streaming response
    return StreamingResponse(
        stream_prd_analysis(prd_content, prd_title, prd_type, db, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.get("/test")
async def test_analysis():
    """Test endpoint to verify the analysis service is working."""
    return {"status": "PRD Analysis service is running", "version": "2.0"} 