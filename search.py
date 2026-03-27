from ddgs import DDGS

def perform_web_search(query):
    """Silently searches DuckDuckGo and returns the top 3 results."""
    print(f"\n[System: Skikai is searching the web for -> '{query}']...")
    
    try:
        # Grab the top 3 text results using the new library
        results = DDGS().text(query, max_results=3)
        
        if not results:
            return "No results found on the web."

        # Format the results into a readable context block
        search_context = f"Live Web Search Results for '{query}':\n"
        for i, res in enumerate(results):
            # Using .get() prevents crashes if the search engine changes its dictionary keys
            title = res.get('title', 'Unknown Title')
            body = res.get('body', 'No description available.')
            search_context += f"{i+1}. {title} - {body}\n"

        print("[System: Web search complete.]")
        return search_context
        
    except Exception as e:
        print(f"[Search Error: {e}]")
        return "Search failed due to an internet error."