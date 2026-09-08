from cognee.infrastructure.engine import DataPoint
from cognee.modules.engine.models.node_set import NodeSet
from cognee.infrastructure.engine.utils.generate_node_id import generate_node_id


class EdgeType(DataPoint):
    relationship_name: str
    number_of_edges: int

    # identity_fields makes the id deterministic and namespaced by class
    # (uuid5 of "EdgeType:<normalized relationship_name>") — same mechanism as
    # Entity/EntityType. EdgeType.id_for(text) is the single way to compute a
    # point id for lookups (retrieval joins, delete flows, adapters).
    metadata: dict = {
        "index_fields": ["relationship_name"],
        "identity_fields": ["relationship_name"],
    }

    def __init__(self, **data):
        super().__init__(**data)
        # Derive belongs_to_set from the relationship's source/target nodes if available
        # This will be set by the caller after checking node sets
