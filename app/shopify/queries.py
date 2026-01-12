"""
GraphQL query strings for Shopify Admin API.
"""


def build_orders_bulk_query(since_date: str) -> str:
    """
    Build bulk operation query for fetching orders.
    
    Args:
        since_date: ISO format date string (e.g., "2024-11-01")
        
    Returns:
        Complete bulkOperationRunQuery mutation string
    """
    return f'''
    mutation {{
      bulkOperationRunQuery(
        query: """
        {{
          orders(query: "created_at:>={since_date}") {{
            edges {{
              node {{
                id
                createdAt
                lineItems {{
                  edges {{
                    node {{
                      product {{
                        id
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
      ) {{
        bulkOperation {{
          id
          status
        }}
        userErrors {{
          field
          message
        }}
      }}
    }}
    '''


def build_products_bulk_query() -> str:
    """
    Build bulk operation query for fetching all active products.
    
    Returns:
        Complete bulkOperationRunQuery mutation string
    """
    return '''
    mutation {
      bulkOperationRunQuery(
        query: """
        {
          products(query: "status:active") {
            edges {
              node {
                id
                createdAt
                variants {
                  edges {
                    node {
                      id
                      price
                      compareAtPrice
                    }
                  }
                }
              }
            }
          }
        }
        """
      ) {
        bulkOperation {
          id
          status
        }
        userErrors {
          field
          message
        }
      }
    }
    '''


# Query to poll bulk operation status
BULK_OPERATION_STATUS_QUERY = '''
query($id: ID!) {
  bulkOperation(id: $id) {
    id
    status
    errorCode
    objectCount
    fileSize
    url
    partialDataUrl
  }
}
'''

# Alternative for older API versions
CURRENT_BULK_OPERATION_QUERY = '''
query {
  currentBulkOperation {
    id
    status
    errorCode
    objectCount
    fileSize
    url
    partialDataUrl
  }
}
'''
