# Development Tasks

## Current Sprint: Agentic PRD Review using RAG from Notion documents
### Task-1: Extract Research, Analytics, and PRDs from Notion to store in the app's vector database as embedding
- [ ] A user should be able to provide a Notion Token on "Settings" page
- [ ] A user should be able to specify Notion's database that has PRDs
- [ ] A user should be able to specify Notion's database that has User Research
- [ ] A user should be able to specify Notion's database that has Data Analytics initiatives and reports
- [ ] A user should be able to confirm the selection
- [ ] The system should save all pages, their content, and associated comments in the database; page's subpages should also be saved.
- [ ] The system should then embed all saved pages (and subpages), their content, and comments and store in vector database (also psql if it supports the vector / RAG use case)
- [ ] The user should see the status of the export / embeddings
- [ ] If user wants to update databases (e.g., there was new content in Notion), the system should only retrieve, store, and embed new content, not the one that already exists
- [ ] A user should see all page names, but not their content, on "your knowledge base" page



### Task 16: Advanced AI Features (FUTURE)
- [ ] Message streaming for real-time responses
- [ ] File upload and processing capabilities
- [ ] Export chat conversations (PDF, JSON)
- [ ] Advanced conversation analytics
- [ ] Custom AI personality settings
- [ ] Message search functionality
