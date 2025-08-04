## Loom Demo
Loom demo: https://www.loom.com/share/c425c8ded92f4ab98ffc39de862146fe

# PRD Review service based on internal knowledge base
## Audience
Product Managers who fear missing on key research or data insights in their product experiences
Product Managers new to the company who do not have all the relevant context about their audience, problem space, and accumulated product org’s knowledge
PM Leaders who want to have a quick way to evaluate quality of PRDs in their org & semi-automatically highlight issues in new product experiences

## Problem
**Context:** Product Requirements Document is a well-accepted format of writing down all the context about the planned product experience, but, following the maxim of “garbage in, garbage out”, badly written PRDs lead to wasted time and missed success measurements. 

PRD is as good as thinking and research that went into it, and PMs may miss critical knowledge that already exists in the company (in research or analytics write-ups). The consequence of writing a PRD that goes against research/data or misses critical pieces known from research, is wasted engineering effort, second-order consequences (overall negative impact on the whole product), and lack of career promotion. 

## Solution
PRD Review AI service that provides evidence and citations for PRD’s content on aligning or violating research and data insights from the internal knowledge base. Solution integrates with a knowledge base provider (e.g., Notion), allows to manually upload documents, and generates additional product and design ideas based on web search.

**Stack:**
1. LLM: OpenAI is a primary provider for LLM capabilities.
2. Embedding Model: text-embedding-3-small from OpenAI.
3. Orchestration: LangGraph. Multi-level orchestration that invokes tools (RAG, Web search).
4. Vector Database: pgvector. Persistent vector storage is used for prototype to showcase the full benefit of data integration.
5. Monitoring: LangSmith’s tracing. 
6. Evaluation: RAGAS to evaluate RAG-specific metrics on a synthetic dataset. Continuous evaluation (LLM-as-a-Judge or Human Annotation) based on production traces is postponed to the post-prototype phase.
7. User Interface: Simple react interface with available PRDs, PRD content, and evaluation in the sidebar. 

**Agentic**
The solution utilises LangGraph to build the orchestration. Agents are simple and mainly perform the evaluation job based on the provided context (RAG, agentic search). Deeper agent involvement is postponed to the post-prototype phase, where they will be used to also build a section analysis plan. Current implementation resembles the DeepResearch architecture more. 

## Dealing with the data
**Data sources and external APIs:**
1. Notion API: retrieve documents from the internal knowledge base to be used in RAG. This will enable our solution to assess whether PRD utilises research insights or contradicts them.
2. Tavily Web Search: retrieve web search results. This will allow our solution to generate ideas based on web research to further integrate into the PRD.
3. Naive retriever: will simply look for the most similar documents (chunks) and return them. This will serve as a baseline. For my case, I’d probably start from Parent Doc Retriever, but for purposes described below, I don’t need it yet. 

**Default chunking:**
After some experimentation, I decided **not to chunk research documents**. While this approach may be contrary to best practices due to increased token spend in a broader context and decreased quality of embeddings, I generally expect research/analytics write-ups to be 2-3 pages long. Additionally, I do not anticipate a large volume of documents to be stored, which makes chunking less crucial. 

If I were to scale it to production, I’d use Parent Doc Retriever to return full documents into context while ensuring the high quality of embeddings via a regular chunking strategy. 

## E2E RAG Prototype
✅Deployed & delivered.

## Golden Test Data Set
| Metric            | Naive Retriever | 
| :---------------: | :-------------: |
| Answer Relevancy  | 0.853           |
| Context Precision | 0.44            |
| Context Recall    | 0.55            |

**Conclusions:**
1. Vibechecking quickly indicated that the context is being properly returned, but the number of tokens / cost is very high. 
2. Low Precision/Recall seems to also be a quirk of both my pipeline (it's not exactly a generic RAG pipeline, but a much more involved one) and chunking (or non-chunking) strategy. I don't think these scores accurately represent RAG quality. I'm running RAGAS at the end, and I can see that I should've performed evaluation differently, e.g., disaggregated the overall pipeline in sub-pipelines, and did focused evals. I should've isolated retrieval steps from the pipeline. 
3. Overall, I'm mostly relying on vibechecking here for now in the prototyping stage. I'm post-prototype I'll implement retrieval-focused evaluation without other parts of the pipeline.


## The Benefits of Advanced Retrieval
**Retrieval techniques:**
1. Naive retriever: this is my baseline. 
2. Compression Retriever based on rerank-3.5. I’m using reranker to improve the quality of the context received by the agent writing the report. Given that I pass full documents as context, I can’t send many. Thus, I need a compression to ensure the most important content gets to the writing agent. 
3. Parent Doc Retriever: Post-prototype, if I were to scale that, I’d be testing Parent Doc Retriever vs. Naive Retriever to ensure we can improve quality of embeddings for chunks, get more accurate documents, but still pass full research information into context. 
## Final Performance Assessment
| Metric            | Naive Retriever | Compression |
| :---------------: | :-------------: | :---------: |
| Answer Relevancy  | 0.853           |  0.836      |
| Context Precision | 0.444           |  0.333      |
| Context Recall    | 0.555           |  0.222      | 

**Conclusions:**
1. Vibechecking quickly indicated that the context is being properly returned, but the number of tokens / cost is very high. 
2. Low Precision/Recall seems to also be a quirk of both my pipeline (it's not exactly a generic RAG pipeline, but a much more involved one) and chunking (or non-chunking) strategy. I don't think these scores accurately represent RAG quality. I'm running RAGAS at the end, and I can see that I should've performed evaluation differently, e.g., disaggregated the overall pipeline in sub-pipelines, and did focused evals. I should've isolated retrieval steps from the pipeline. 
3. Overall, I'm mostly relying on vibechecking here for now in the prototyping stage. I'm post-prototype I'll implement retrieval-focused evaluation without other parts of the pipeline.
4. Given the approach I used in the prototype where I return the whole documen into the context, essentially having each chunk equal to document, there isn't much of a difference with/without compression. Reranker performs a bit worse on a low sample because reranking big chunks isn't really a thoughtful strategy. 
5. I'll be moving to Parent Doc Retrieval to emulate my approach with Naive Retriever but at higher quality of retrieval via more precise embeddings.
6. Overall, I should've thought-through my RAG Eval approach from early stages; instead, I did it at the end, and focused on trying to fit the whole pipeline into RAG-specific Evals. Bad decision, short on time. Should've EVALed RAG part separately, and then performed regular LLM-as-a-Judge Evals separately from RAGAS. 

**Next steps:**
1. Fix bug with manual doc upload. Notion API sync works well, but upload has a bug. 
2. Re-build Notion API sync to use parallel processing, as Notion provides data from pages in blocks, which really slows down the export. Notion MCP is not a good choice as it will pre-filter the data for us, while we need full access to run our pipeline. 
3. Improve prompting for section analysis agents: make them more concise, better targeted at specific ideas, etc.
4. Improve UI: parse final report into sections for readability (or ditch final report assembly in favour of just working with sections).
5. Add “Chat to knowledge base”: provide ability to ask additional questions within PRD and outside of, doing RAG over knowledge base. 
6. Improve UI of the PRD content view.
7. Add better markdown styling for PRDs created in the app.
8. Add PRDs into RAG context as a separate pipeline step to ensure no collision between product initiatives happen. 
9. Fix RAGAS issues. 
10. Improve overall UI: it’s a mess. 





