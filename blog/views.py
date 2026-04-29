from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Post

def blog_list(request):
    """Blog listing page - matches blog.html"""
    posts = Post.objects.filter(is_published=True).order_by('-created_at')
    
    # Simple filtering by category (if you add categories later)
    category = request.GET.get('category')
    if category:
        posts = posts.filter(category__slug=category)
    
    # Pagination
    paginator = Paginator(posts, 10)  # 10 posts per page
    page = request.GET.get('page', 1)
    posts_page = paginator.get_page(page)
    
    context = {
        'posts': posts_page,
        'categories': [],  # Add if you create Category model for blog
    }
    return render(request, 'blog/list.html', context)

def blog_detail(request, slug):
    """Single blog post"""
    post = get_object_or_404(Post, slug=slug, is_published=True)
    
    # Related posts
    related = Post.objects.filter(
        is_published=True,
        category=post.category
    ).exclude(id=post.id)[:3] if hasattr(post, 'category') else []
    
    context = {
        'post': post,
        'related_posts': related,
    }
    return render(request, 'blog/detail.html', context)