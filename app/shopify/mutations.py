"""
GraphQL mutation strings for Shopify Admin API.
"""


# Mutation to update variant prices
PRODUCT_VARIANTS_BULK_UPDATE = '''
mutation productVariantsBulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      compareAtPrice
    }
    userErrors {
      field
      message
    }
  }
}
'''
