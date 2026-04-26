from django.http import JsonResponse

def home(request):
    return JsonResponse({
        'message': 'Welcome to PAYLOFT- Transaction-Based POS System',
        'version': '1.0',
        'endpoints': {
            'api': '/api/',
            'admin': '/admin/',
            'products': '/api/products/',
            'sales': '/api/sales/',
            'create_sale': '/api/sales/create_sale/'
        },
        'frontend': 'http://localhost:3000',
        'documentation': 'See README.md for setup instructions'
    })
