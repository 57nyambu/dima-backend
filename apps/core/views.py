from django.views.generic import TemplateView, DetailView
from apps.products.models import Product
from django.db.models import Count, Avg
from django.shortcuts import get_object_or_404
from django.views import View
from django.shortcuts import render
import requests
BASE_URL = "http://127.0.0.1:8000/api/"

class LandingView(TemplateView):
    template_name = "landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all active products with images
        context['products'] = Product.objects.filter(
            is_active=True
        ).select_related(
            'business',
            'category'
        ).prefetch_related(
            'images'
        ).order_by('-created_at')[:12]  # Latest 12 products

        return context

#class NewLandingView(TemplateView):
#    template_name = "marketplace/default_landing.html"

# views.py
class NewLandingView(View):
    template_name = "marketplace/landing.html"
    
    def get(self, request):
        # Fetch categories from the API
        categories_url = f'{BASE_URL}marketplace/categories/'  # Updated URL
        # Fetch other data from backend API
        api_url = f'{BASE_URL}marketplace/home/'  # Updated URL
        
        try:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Fetch categories
            try:
                categories_response = requests.get(categories_url, headers=headers)
                categories = categories_response.json() if categories_response.status_code == 200 else []
            except (requests.RequestException, ValueError) as e:
                print(f"Categories API error: {e}")
                categories = []
            
            # Fetch other data
            try:
                response = requests.get(api_url, headers=headers)
                data = response.json() if response.status_code == 200 else {}
            except (requests.RequestException, ValueError) as e:
                print(f"Home API error: {e}")
                data = {}
            
            # Process featured and trending products
            featured_products = []
            trending_products = []
            
            # Safely process featured products
            for product in data.get('featured_products', []):
                try:
                    if 'images' in product:
                        for image in product['images']:
                            for key in ['original', 'medium', 'thumbnail']:
                                if key in image and isinstance(image[key], bytes):
                                    try:
                                        image[key] = image[key].decode('utf-8')
                                    except UnicodeDecodeError:
                                        del image[key]
                    featured_products.append(product)
                except Exception as e:
                    print(f"Error processing featured product: {e}")
            
            # Safely process trending products
            for product in data.get('trending_products', []):
                try:
                    if 'images' in product:
                        for image in product['images']:
                            for key in ['original', 'medium', 'thumbnail']:
                                if key in image and isinstance(image[key], bytes):
                                    try:
                                        image[key] = image[key].decode('utf-8')
                                    except UnicodeDecodeError:
                                        del image[key]
                    trending_products.append(product)
                except Exception as e:
                    print(f"Error processing trending product: {e}")
            
            return render(request, self.template_name, {
                'banners': data.get('banners', []),
                'featured_products': featured_products,
                'top_vendors': data.get('top_vendors', []),
                'trending_products': trending_products,
                'categories': categories,
            })
            
        except Exception as e:
            print(f"Unexpected error in landing view: {e}")
            # Fallback if API is not available
            return render(request, self.template_name, {
                'banners': [],
                'featured_products': [],
                'top_vendors': [],
                'trending_products': [],
                'categories': []
            })

#class NewProductDetailView(TemplateView):
#    template_name = "marketplace/product_details.html"

# views.py
class NewProductDetailView(View):
    template_name = 'marketplace/product_details.html'
    
    def get(self, request, slug):
        # Fetch product data from backend API
        api_url = f'{BASE_URL}marketplace/api/products/{slug}/'  # Removed 'marketplace/' from URL
        
        try:
            # Add headers to ensure proper JSON response
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                try:
                    product_data = response.json()
                    # Ensure proper URL formatting for images
                    if product_data.get('images'):
                        for image in product_data['images']:
                            # Convert any binary data to proper URLs
                            for key in ['original', 'medium', 'thumbnail']:
                                if key in image and isinstance(image[key], bytes):
                                    try:
                                        image[key] = image[key].decode('utf-8')
                                    except UnicodeDecodeError:
                                        # If decoding fails, remove the problematic field
                                        del image[key]
                    
                    return render(request, self.template_name, {
                        'product': product_data
                    })
                except ValueError as e:
                    print(f"JSON decode error: {e}")
                    return render(request, 'marketplace/error.html', {
                        'message': 'Invalid data received from server'
                    }, status=500)
            elif response.status_code == 404:
                return render(request, 'marketplace/404.html', status=404)
            else:
                return render(request, 'marketplace/error.html', {
                    'message': f'Server returned status code {response.status_code}'
                }, status=response.status_code)
                
        except requests.RequestException as e:
            print(f"API connection error: {e}")
            return render(request, 'marketplace/error.html', {
                'message': 'Unable to connect to the server'
            }, status=503)

class ProductDetailView(DetailView):
    model = Product
    template_name = 'marketplace/default_product_detail.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True
        ).select_related(
            'business',  # For vendor info
            'category'   # For breadcrumb
        ).prefetch_related(
            'images',
            'category__children'  # For category breadcrumb
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Update product view count
        if hasattr(self.object, 'search_index'):
            self.object.increase_view_count()
            
        return context

class DocumentationView(TemplateView):
    template_name = "docs/index.html"