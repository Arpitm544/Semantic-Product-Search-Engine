"""Atlas vector retrieval using the same encoder as the local reranker pipeline."""
import os


def index_name():
    return os.getenv('ATLAS_VECTOR_INDEX', 'product_vectors')


def collection_name(generation):
    # Separate generations prevent queries mixing catalog versions or model weights.
    return 'product_vectors_' + generation


def index_definition(dimensions):
    return {'fields': [{'type': 'vector', 'path': 'embedding',
                        'numDimensions': dimensions, 'similarity': 'cosine'}]}


class AtlasVectorSearch:
    def __init__(self, db, products, encoder, model_name, generation):
        self.model_name = model_name
        self.encoder = encoder
        self.by_id = {p['id']: p for p in products}
        self.collection = db[collection_name(generation)]
        metadata = db['vector_manifests'].find_one({'_id': generation})
        if not metadata or metadata.get('status') != 'ready' or metadata.get('product_count') != len(products):
            raise RuntimeError('Atlas vectors are missing or outdated. Run scripts/setup_atlas_vectors.py.')
        indexes = list(self.collection.list_search_indexes(name=index_name()))
        dimensions = encoder.get_sentence_embedding_dimension()
        if (not indexes or not indexes[0].get('queryable')
                or indexes[0].get('latestDefinition') != index_definition(dimensions)):
            raise RuntimeError('Atlas vector index is not ready or has a different definition. Run scripts/setup_atlas_vectors.py.')

    def search(self, query, top_k=10):
        if top_k <= 0:
            return []
        limit = min(top_k, len(self.by_id))
        if not limit:
            return []
        vector = self.encoder.encode([query], normalize_embeddings=True,
                                     show_progress_bar=False)[0].tolist()
        pipeline = [
            {'$vectorSearch': {'index': index_name(), 'path': 'embedding',
                              'queryVector': vector, 'numCandidates': max(100, limit * 20),
                              'limit': limit}},
            {'$project': {'_id': 0, 'id': 1, 'score': {'$meta': 'vectorSearchScore'}}},
        ]
        rows = self.collection.aggregate(pipeline, maxTimeMS=30000)
        return [(self.by_id[row['id']], float(row['score']))
                for row in rows if row['id'] in self.by_id]
