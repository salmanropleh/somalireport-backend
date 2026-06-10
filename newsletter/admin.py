"""
Admin configuration for newsletter app.
"""

from django.contrib import admin
from .models import Newsletter, NewsletterSubscription, NewsletterRead


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    """Admin configuration for Newsletter model."""

    list_display = [
        'title', 'subject', 'status', 'sent_at',
        'recipient_count', 'open_count', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'sent_at']
    search_fields = ['title', 'subject', 'excerpt']
    readonly_fields = [
        'slug', 'sent_at', 'recipient_count', 'open_count',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'subject', 'excerpt')
        }),
        ('Content', {
            'fields': ('content_html', 'content_text', 'featured_image')
        }),
        ('Status', {
            'fields': ('status', 'sent_at', 'recipient_count', 'open_count')
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    """Admin configuration for NewsletterSubscription model."""

    list_display = [
        'email', 'user', 'is_active', 'created_at', 'unsubscribed_at'
    ]
    list_filter = ['is_active', 'created_at', 'unsubscribed_at']
    search_fields = ['email', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'unsubscribe_token', 'created_at', 'updated_at', 'unsubscribed_at'
    ]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Subscriber Information', {
            'fields': ('email', 'user')
        }),
        ('Status', {
            'fields': ('is_active', 'unsubscribe_token', 'unsubscribed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(NewsletterRead)
class NewsletterReadAdmin(admin.ModelAdmin):
    """Admin configuration for NewsletterRead model."""

    list_display = ['newsletter', 'subscription', 'read_at']
    list_filter = ['read_at', 'newsletter']
    search_fields = ['subscription__email', 'newsletter__title']
    readonly_fields = ['read_at']
    date_hierarchy = 'read_at'
