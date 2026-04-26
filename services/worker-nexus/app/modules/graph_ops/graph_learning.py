"""
OpenQ Nexus: Graph Representation Learning (GRL) Pipeline
Engineered for Neo4j GDS 2.x+
"""

import asyncio
import structlog
from typing import Dict, Any, List
from graphdatascience import GraphDataScience
from app.infrastructure.config import settings

# Import the real Celery app — do NOT create a dummy instance here.
# A second Celery() call would register tasks on a disconnected broker.
from app.worker import celery_app  # noqa: E402

# Initialize structured logging
logger = structlog.get_logger(__name__)

class GDSMaintenanceSession:
    """
    Context manager to ensure GDS graph projections are cleaned up.
    Prevents Neo4j heap/off-heap memory leaks during pipeline failures.
    """
    def __init__(self, gds: GraphDataScience, graph_name: str):
        self.gds = gds
        self.graph_name = graph_name
        self.G = None

    def __enter__(self):
        # Drop if exists to ensure a fresh projection for this maintenance cycle
        if self.gds.graph.exists(self.graph_name).exists:
            self.gds.graph.get(self.graph_name).drop()
        return self

    def project(self, node_labels: List[str], rel_config: Dict[str, Any]):
        self.G, _ = self.gds.graph.project(self.graph_name, node_labels, rel_config)
        return self.G

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.G:
            self.G.drop()
            logger.info("gds_graph_dropped", graph_name=self.graph_name)

def _execute_gds_sync_logic() -> Dict[str, Any]:
    """
    Synchronous GDS logic executed in a separate thread.
    Captures structural topology and predicts cross-pillar links.
    """
    gds = GraphDataScience(
        settings.NEO4J_URI, 
        auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
    )
    
    graph_name = "nexus_knowledge_graph"
    lp_pipeline_name = "pillar_bridge_pipeline"
    model_name = "nexus_link_predictor"
    
    # 1. Resource Management Lifecycle
    with GDSMaintenanceSession(gds, graph_name) as session:
        logger.info("gds_projection_started")
        
        # Projecting multi-modal schema
        # We use UNDIRECTED for structural similarity as the flow of information
        # in a Knowledge Graph is often bidirectional for context.
        G = session.project(
            ["Document", "Chunk", "Entity", "Class", "Function", "Table", "Column", "Speaker", "Turn"],
            {
                "FROM_DOCUMENT": {"orientation": "UNDIRECTED"},
                "NEXT_CHUNK": {"orientation": "DIRECTED"},
                "DEFINED_IN": {"orientation": "UNDIRECTED"},
                "HAS_FUNCTION": {"orientation": "UNDIRECTED"},
                "CALLS": {"orientation": "DIRECTED"},
                "IMPORTS": {"orientation": "DIRECTED"},
                "HAS_COLUMN": {"orientation": "UNDIRECTED"},
                "FOREIGN_KEY_TO": {"orientation": "DIRECTED"},
                "SPOKE": {"orientation": "UNDIRECTED"},
                "MENTIONS": {"orientation": "UNDIRECTED"},
                "FROM_SESSION": {"orientation": "UNDIRECTED"},
                "NEXT_TURN": {"orientation": "DIRECTED"}
            }
        )

        # 2. FastRP (Fast Random Projection)
        # Theory: Unlike Node2Vec which uses random walks, FastRP uses sparse random 
        # projections to preserve graph distances. It is O(N) and captures 
        # global topology much faster for billion-scale graphs.
        logger.info("gds_fast_rp_running")
        gds.fastRP.mutate(
            G,
            mutateProperty="structural_embedding",
            embeddingDimension=256,
            iterationWeights=[0.8, 1.0, 1.0], # Emphasizing local and mid-range neighbors
            randomSeed=42
        )
        
        # Write back embeddings so downstream RAG applications can use them for 
        # "Structural Similarity Search" (finding code similar to text docs).
        gds.graph.writeNodeProperties(G, ["structural_embedding"])

        # 3. Link Prediction Pipeline
        # We want to predict if a 'Chunk' (text) should link to a 'Class' (code).
        try:
            # Cleanup old pipelines/models if they exist
            if gds.beta.pipeline.linkPrediction.exists(lp_pipeline_name).exists:
                gds.beta.pipeline.linkPrediction.get(lp_pipeline_name).drop()
            
            pipe, _ = gds.beta.pipeline.linkPrediction.create(lp_pipeline_name)
            
            # Use the FastRP embeddings as the feature source
            pipe.addNodeProperty("structural_embedding", mutateProperty="structural_embedding")
            
            # Add Hadarmard feature: combines two node embeddings into a single link vector
            pipe.addLinkFeature("hadamard", nodeProperties=["structural_embedding"])
            
            pipe.configureSplit(testFraction=0.2, trainFraction=0.1, validationFolds=3)
            
            # Using Random Forest for non-linear relationships between pillars
            pipe.addRandomForest(numberOfDecisionTrees=10)
            
            logger.info("gds_lp_training_started")
            model, _ = pipe.train(G, modelName=model_name, targetRelationshipType="MENTIONS")
            
            # 4. Predict and Mutate
            # Apply the model to predict missing links across the whole graph
            predict_result = gds.beta.pipeline.linkPrediction.predict.mutate(
                G,
                modelName=model_name,
                mutateRelationshipType="INFERRED_LINK_GRL",
                threshold=0.85 # High confidence only
            )
            
            # Write inferred relationships back to Neo4j
            gds.graph.writeRelationship(G, "INFERRED_LINK_GRL")
            
            lp_stats = {
                "links_inferred": predict_result.get("relationshipsWritten", 0),
                "model_accuracy": model.metrics().get("test", {}).get("auprc", 0)
            }
            
        except Exception as lp_err:
            logger.warning("link_prediction_skipped", reason=str(lp_err))
            lp_stats = {"status": "skipped"}

        return {
            "nodes": G.node_count(),
            "relationships": G.relationship_count(),
            "lp_stats": lp_stats
        }

@celery_app.task(name="graph_ops.run_gds_maintenance", ack_late=True)
def run_gds_maintenance_task():
    """Celery entry point."""
    return asyncio.run(run_graph_learning_pipeline())

async def run_graph_learning_pipeline() -> Dict[str, Any]:
    """
    Asynchronous wrapper for GDS maintenance.
    Offloads heavy blocking CPU/Network IO to a thread pool.
    """
    log = logger.bind(pipeline="GRL_Maintenance")
    log.info("pipeline_started")
    
    try:
        # run_in_executor allows the async Celery worker to handle other 
        # heartbeat/task signals while the GDS heavy lifting happens.
        loop = asyncio.get_running_loop()
        stats = await loop.run_in_executor(None, _execute_gds_sync_logic)
        
        log.info("pipeline_completed", stats=stats)
        return {"status": "success", "data": stats}
        
    except Exception as e:
        log.error("pipeline_failed", error=str(e), exc_info=True)
        return {"status": "error", "message": str(e)}