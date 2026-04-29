from django.db import models
from django.utils.text import slugify
from common.models import BaseModel

class Post(BaseModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    meta_description = models.TextField(max_length=160, blank=True)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='blog/%Y/%m/', null=True, blank=True)
    is_published = models.BooleanField(default=False)
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    def __str__(self): return self.title