# blog/models.py
from django.db import models
from django.utils.text import slugify
from common.models import BaseModel

class BlogCategory(BaseModel):
    """Categories for Blog Posts (e.g., Fashion, Men, Women, Guides)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Blog Categories'
        ordering = ['name']

class Post(BaseModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    
    # ✅ NEW: Link to Category
    category = models.ForeignKey(
        BlogCategory, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='posts'
    )
    
    meta_description = models.TextField(max_length=160, blank=True)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='blog/%Y/%m/', null=True, blank=True)
    is_published = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title