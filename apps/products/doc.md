# E-commerce API Documentation

## Base URL
`http://localhost:8000/api/`

## Authentication
Not implemented in current version. All endpoints are publicly accessible.

## Endpoints

### Categories

#### List Categories
- **GET** `/categories/`
- Returns all categories
- Response: List of category objects
```json
[
    {
        "id": 1,
        "name": "Electronics",
        "slug": "electronics",
        "description": "Electronic items",
        "parent": null
    }
]
```

#### Create Category
- **POST** `/categories/`
- Request Body:
```json
{
    "name": "Electronics",
    "description": "Electronic items",
    "parent": null
}
```

#### Update Category
- **PUT/PATCH** `/categories/{slug}/`
- Request Body (PUT - full update):
```json
{
    "name": "Electronics Updated",
    "description": "Updated description",
    "parent": null
}
```

### Products

#### List Products
- **GET** `/products/`
- Returns all products
- Response: List of product objects
```json
[
    {
        "id": 1,
        "category": {
            "id": 1,
            "name": "Electronics",
            "slug": "electronics",
            "description": "Electronic items",
            "parent": null
        },
        "name": "Laptop",
        "slug": "laptop",
        "description": "Powerful laptop",
        "price": "999.99",
        "compare_price": "1299.99",
        "stock_qty": 10,
        "is_active": true,
        "images": []
    }
]
```

#### Create Product
- **POST** `/products/`
- Request Body:
```json
{
    "category_id": 1,
    "name": "New Laptop",
    "description": "Latest model",
    "price": "1299.99",
    "compare_price": "1499.99",
    "stock_qty": 5,
    "is_active": true
}
```

#### Update Product
- **PUT/PATCH** `/products/{slug}/`
- For PATCH, include only fields to update
- Request Body (PUT):
```json
{
    "category_id": 1,
    "name": "Updated Laptop",
    "description": "Updated description",
    "price": "1199.99",
    "compare_price": "1399.99",
    "stock_qty": 8,
    "is_active": true
}
```

### Product Images

#### List Images
- **GET** `/product-images/`
- Returns all product images

#### Upload Image
- **POST** `/product-images/`
- Content-Type: multipart/form-data
- Form Fields:
  - image: file
  - alt_text: string
  - is_feature: boolean

## Testing Examples

### Using cURL

```bash
# List all products
curl http://localhost:8000/api/products/

# Create a category
curl -X POST http://localhost:8000/api/categories/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Electronics","description":"Electronic items"}'

# Create a product
curl -X POST http://localhost:8000/api/products/ \
  -H "Content-Type: application/json" \
  -d '{
    "category_id": 1,
    "name": "New Laptop",
    "description": "Latest model",
    "price": "1299.99",
    "stock_qty": 5,
    "is_active": true
  }'
```

### Using Python Requests

```python
import requests

BASE_URL = 'http://localhost:8000/api'

# List products
response = requests.get(f'{BASE_URL}/products/')
products = response.json()

# Create product
new_product = {
    "category_id": 1,
    "name": "New Laptop",
    "description": "Latest model",
    "price": "1299.99",
    "stock_qty": 5,
    "is_active": True
}
response = requests.post(f'{BASE_URL}/products/', json=new_product)
```