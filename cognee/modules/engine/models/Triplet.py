from cognee.infrastructure.engine import DataPoint
from cognee.modules.engine.models.node_set import NodeSet


class Triplet(DataPoint):
    text: str
    from_node_id: str
    to_node_id: str

    metadata: dict = {"index_fields": ["text"]}

    def __init__(self, **data):
        super().__init__(**data)
        # Derive belongs_to_set from the triplet's source/target nodes if available
        # This will be set by the caller after checking node sets
