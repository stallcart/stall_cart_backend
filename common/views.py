# common/views.py
from django.shortcuts import render
from django.http import HttpResponse

def custom_404(request, exception=None):
    """Page Not Found"""
    return render(request, 'errors/404.html', status=404)

def custom_403(request, exception=None):
    """Permission Denied"""
    return render(request, 'errors/403.html', status=403)

def custom_400(request, exception=None):
    """Bad Request"""
    return render(request, 'errors/400.html', status=400)

def custom_500(request):
    """Server Error (Fallback)"""
    # Return plain HTML to avoid cascading failures if base.html breaks
    return HttpResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Something Went Wrong</title>
        <style>
            body { font-family: system-ui, sans-serif; margin: 0; padding: 0; 
                   background: #f8f9fa; color: #333; text-align: center; }
            .error-container { min-height: 100vh; display: flex; flex-direction: column; 
                               align-items: center; justify-content: center; padding: 20px; }
            .icon { font-size: 5rem; margin-bottom: 20px; }
            h1 { font-size: 2rem; margin: 0 0 10px; }
            p { max-width: 500px; color: #666; margin-bottom: 30px; }
            .btn { display: inline-block; padding: 12px 24px; background: #2874f0; 
                   color: white; text-decoration: none; border-radius: 8px; font-weight: 600; }
            .btn:hover { background: #1a56c4; }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="icon">⚠️</div>
            <h1>Oops! Something went wrong</h1>
            <p>We're sorry, but an unexpected error occurred. Our team has been notified. Please try again later.</p>
            <a href="/" class="btn">Go to Homepage</a>
        </div>
    </body>
    </html>
    """, status=500)