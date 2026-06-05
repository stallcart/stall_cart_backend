from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import SiteSettings, EmailTemplate

class BaseModelAdmin(admin.ModelAdmin):
    """Reusable admin config for all models inheriting BaseModel"""
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'is_active')
    list_filter = ('is_active', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Auto-filter by created_by for non-superusers (optional)
        if not request.user.is_superuser and hasattr(qs.model, 'created_by'):
            return qs.filter(created_by=request.user)
        return qs

    def has_change_permission(self, request, obj=None):
        # Allow owners to edit their own objects
        if not request.user.is_superuser and obj and hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        return super().has_change_permission(request, obj)

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Admin for global site branding - singleton pattern"""
    
    # Prevent deletion of the singleton instance
    def has_delete_permission(self, request, obj=None):
        return False
    
    # Display in admin list view
    list_display = ('site_name', 'logo_preview', 'primary_color', 'is_maintenance_mode', 'enable_background_jobs', 'updated_at')
    list_filter = ('is_maintenance_mode', 'enable_background_jobs', 'updated_at')
    search_fields = ('site_name', 'site_tagline')
    readonly_fields = ('created_at', 'updated_at', 'logo_preview', 'favicon_preview', 'jobs_status_control')
    
    # Organize fields into logical sections
    fieldsets = (
        ('🏷️ Basic Info', {
            'fields': ('site_name', 'site_tagline', 'meta_description','about_us')
        }),
        ('🖼️ Logos', {
            'fields': ('logo_primary', 'logo_dark', 'logo_mobile', 'logo_preview'),
            'description': 'Upload high-quality PNG/SVG logos. Recommended: 200-400px wide with transparent background.'
        }),
        ('🔖 Icons', {
            'fields': ('favicon', 'apple_touch_icon', 'favicon_preview')
        }),
        ('🎨 Brand Colors', {
            'fields': ('primary_color', 'secondary_color'),
            'description': 'Use hex codes (e.g., #2874f0). These power CSS variables across the site.'
        }),
        ('📞 Contact', {
            'fields': ('contact_phone', 'contact_email', 'contact_whatsapp')
        }),
        ('🌐 Social Links', {
            'fields': ('social_instagram', 'social_facebook', 'social_twitter', 'social_youtube')
        }),
        ('🚚 Delivery Settings', {
            'fields': ('delivery_charge', 'free_delivery_threshold'),
            'description': 'Configure delivery fees and the free delivery minimum threshold amount (₹).'
        }),
        ('📜 Site Policies', {
            'fields': ('cancellation_policy', 'return_policy', 'terms_conditions', 'privacy_policy'),
            'description': 'Manage site-wide legal policies. Content supports rich text and HTML.'
        }),
        ('⚙️ Site Status & System Settings', {
            'fields': ('is_maintenance_mode', 'enable_background_jobs', 'jobs_status_control', 'daily_email_otp_limit', 'daily_sms_otp_limit', 'slider_autoplay_seconds'),
        }),
        ('📅 Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    class Media:
        js = ('js/admin_richtext.js',)
    
    # Show image preview in admin list
    def logo_preview(self, obj):
        if obj.logo_primary:
            return format_html(
                '<img src="{}" style="max-height:50px; max-width:200px; border-radius:4px; border:1px solid #eee;">',
                obj.logo_primary.url
            )
        return 'No logo uploaded'
    logo_preview.short_description = 'Logo Preview'
    
    # Show favicon preview
    def favicon_preview(self, obj):
        if obj.favicon:
            return format_html(
                '<img src="{}" style="height:32px; width:32px; border-radius:4px; border:1px solid #eee;">',
                obj.favicon.url
            )
        return 'No favicon'
    favicon_preview.short_description = 'Favicon Preview'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('toggle-jobs/', self.admin_site.admin_view(self.toggle_jobs_view), name='common_sitesettings_toggle_jobs'),
        ]
        return custom_urls + urls

    def toggle_jobs_view(self, request):
        obj = SiteSettings.get_singleton()
        obj.enable_background_jobs = not obj.enable_background_jobs
        obj.save(update_fields=['enable_background_jobs'])
        status = "ENABLED" if obj.enable_background_jobs else "DISABLED"
        messages.success(request, f"Background jobs have been successfully {status}!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))

    def jobs_status_control(self, obj):
        status_label = "🟢 Running" if obj.enable_background_jobs else "🔴 Stopped"
        btn_text = "Stop Jobs" if obj.enable_background_jobs else "Start Jobs"
        btn_color = "#dc2626" if obj.enable_background_jobs else "#16a34a"
        url = reverse('admin:common_sitesettings_toggle_jobs')
        
        return format_html(
            '<div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; max-width: 400px;">'
            '  <div style="font-size: 14px; margin-bottom: 12px; color: #1e293b;">Current Status: <strong style="font-size: 15px;">{}</strong></div>'
            '  <a href="{}" class="button" style="background: {}; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;">{}</a>'
            '</div>',
            status_label, url, btn_color, btn_text
        )
    jobs_status_control.short_description = "Background Jobs Control Dashboard"


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'updated_at')
    search_fields = ('name', 'subject', 'body')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')        