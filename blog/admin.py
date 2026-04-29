from django.contrib import admin
from .models import Post
from common.admin import BaseModelAdmin

@admin.register(Post)
class PostAdmin(BaseModelAdmin):
    list_display = ('title', 'slug', 'is_published', 'created_at', 'updated_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Content', {'fields': ('title', 'slug', 'meta_description', 'content', 'featured_image')}),
        ('Publishing', {'fields': ('is_published',)}),
        ('Audit', {'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')}),
    )