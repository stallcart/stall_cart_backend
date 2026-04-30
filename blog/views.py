# blog/views.py
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Count
from .models import Post, BlogCategory
from items.models import Product

def blog_list(request):
    """Blog listing page with dynamic categories"""
    posts = Post.objects.filter(is_published=True).order_by('-created_at')
    
    # ✅ Filter by Category (if selected)
    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)
    
    # Pagination
    paginator = Paginator(posts, 10)
    page = request.GET.get('page', 1)
    posts_page = paginator.get_page(page)
    
    # ✅ Fetch Dynamic Categories with Post Counts
    # Only show categories that have published posts
    categories = BlogCategory.objects.annotate(
        post_count=Count('posts', filter=Q(posts__is_published=True))
    ).filter(post_count__gt=0).order_by('name')
    
    # Fetch Hot/Trending Products
    hot_products = Product.objects.filter(
        status='published', stock__gt=0, is_hot_deal=True
    ).select_related('seller', 'category').prefetch_related('product_image_product')[:4]
    
    trending_products = Product.objects.filter(
        status='published', stock__gt=0
    ).order_by('-views_count', '-sold_count', '-created_at')[:4]
    
    context = {
        'posts': posts_page,
        'categories': categories,  # ✅ Dynamic categories
        'active_category': category_slug,
        'hot_products': hot_products,
        'trending_products': trending_products,
    }
    return render(request, 'blog/list.html', context)

def blog_detail(request, slug):
    """Single blog post"""
    post = get_object_or_404(Post, slug=slug, is_published=True)
    
    related = Post.objects.filter(
        is_published=True,
        category=post.category  # Same category
    ).exclude(id=post.id).order_by('-created_at')[:3] if post.category else []
    
    # Fallback products
    related_products = Product.objects.filter(
        status='published', stock__gt=0
    ).order_by('-views_count')[:4]
    
    context = {
        'post': post,
        'related_posts': related,
        'related_products': related_products,
    } 
    return render(request, 'blog/detail.html', context)