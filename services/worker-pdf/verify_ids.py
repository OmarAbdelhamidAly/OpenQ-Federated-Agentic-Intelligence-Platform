"""Diagnostic script to verify ID alignment between Qdrant and Neo4j.
Ensures that every vector in Qdrant has a corresponding node in Neo4j.
"""
import asyncio
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from app.infrastructure.config import settings

async def verify_id_alignment(collection_name: str):
    print(f"--- Verifying ID alignment for collection: {collection_name} ---")
    
    # 1. Connect to Qdrant
    q_client = QdrantClient(url=settings.QDRANT_URL or "http://localhost:6333")
    
    # 2. Connect to Neo4j
    n_driver = GraphDatabase.driver(
        settings.NEO4J_URI, 
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    
    try:
        # Fetch all IDs from Qdrant
        print("Fetching points from Qdrant...")
        points = q_client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=False,
            with_vectors=False
        )[0]
        
        q_ids = {str(p.id) for p in points}
        print(f"Found {len(q_ids)} points in Qdrant.")
        
        # Verify in Neo4j
        print("Verifying IDs in Neo4j...")
        with n_driver.session() as session:
            # Query for documents linked to these chunks
            result = session.run(
                "MATCH (c:Chunk) RETURN c.chunk_id as chunk_id"
            )
            n_ids = {str(record["chunk_id"]) for record in result}
            
        print(f"Found {len(n_ids)} Chunk nodes in Neo4j.")
        
        # Calculate mismatches
        orphans_in_qdrant = q_ids - n_ids
        orphans_in_neo4j = n_ids - q_ids
        
        if not orphans_in_qdrant and not orphans_in_neo4j:
            print("✅ SUCCESS: All IDs are perfectly aligned!")
        else:
            if orphans_in_qdrant:
                print(f"❌ ERROR: Found {len(orphans_in_qdrant)} points in Qdrant missing from Neo4j.")
                print(f"Examples: {list(orphans_in_qdrant)[:5]}")
            if orphans_in_neo4j:
                print(f"❌ ERROR: Found {len(orphans_in_neo4j)} nodes in Neo4j missing from Qdrant.")
                print(f"Examples: {list(orphans_in_neo4j)[:5]}")
                
    except Exception as e:
        print(f"Verification failed: {str(e)}")
    finally:
        n_driver.close()

if __name__ == "__main__":
    import sys
    coll = sys.argv[1] if len(sys.argv) > 1 else "kb_default"
    asyncio.run(verify_id_alignment(coll))
