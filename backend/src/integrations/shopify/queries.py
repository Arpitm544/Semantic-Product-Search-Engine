PRODUCT_FIELDS = '''id title description productType vendor tags status updatedAt
options { name values }'''
COLLECTION = '''query Catalog($id: ID!, $after: String) {
collection(id: $id) { products(first: 100, after: $after) {
nodes { ''' + PRODUCT_FIELDS + ''' } pageInfo { hasNextPage endCursor }
} } }'''
DETAILS = '''query Details($ids: [ID!]!) { nodes(ids: $ids) { ... on Product {
id title onlineStoreUrl availableForSale featuredImage { url }
priceRange { minVariantPrice { amount currencyCode } maxVariantPrice { amount currencyCode } }
} } }'''
