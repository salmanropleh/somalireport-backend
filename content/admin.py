from django.contrib import admin
from .models import Video, Category, Tag

# Register your models here.

@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """Admin configuration for Video model."""
    list_display = ['title', 'slug', 'status', 'category', 'uploaded_by', 'view_count', 'like_count', 'is_featured', 'created_at']
    list_filter = ['status', 'is_featured', 'category', 'created_at']
    search_fields = ['title', 'description', 'slug']
    readonly_fields = ['slug', 'view_count', 'like_count', 'share_count', 'created_at', 'updated_at']
    filter_horizontal = ['tags']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description')
        }),
        ('Media', {
            'fields': ('video_file', 'thumbnail')
        }),
        ('Relationships', {
            'fields': ('uploaded_by', 'category', 'tags')
        }),
        ('Metadata', {
            'fields': ('duration', 'file_size', 'mime_type')
        }),
        ('Publishing', {
            'fields': ('status', 'published_at', 'allow_comments', 'is_featured')
        }),
        ('Analytics', {
            'fields': ('view_count', 'like_count', 'share_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin configuration for Category model."""
    list_display = ['name', 'slug', 'is_active', 'sort_order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin configuration for Tag model."""
    list_display = ['name', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']
