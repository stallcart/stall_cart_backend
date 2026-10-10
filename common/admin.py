from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import SiteSettings, EmailTemplate, SupportEnquiry, Campaign, CampaignPrize, CampaignParticipant, CampaignWinner
import secrets
from django.shortcuts import get_object_or_404, render, redirect

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
    list_display = ('site_name', 'logo_preview', 'primary_color', 'is_maintenance_mode', 'enable_background_jobs', 'enable_email_backup', 'updated_at')
    list_filter = ('is_maintenance_mode', 'enable_background_jobs', 'enable_email_backup', 'updated_at')
    search_fields = ('site_name', 'site_tagline')
    readonly_fields = ('created_at', 'updated_at', 'logo_preview', 'favicon_preview', 'jobs_status_control', 'email_backup_status_control')
    
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
            'fields': ('is_maintenance_mode', 'enable_background_jobs', 'jobs_status_control', 'enable_email_backup', 'email_backup_status_control', 'daily_email_otp_limit', 'daily_sms_otp_limit', 'otp_expiry_minutes', 'slider_autoplay_seconds'),
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

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            new_fieldsets = []
            for name, opts in fieldsets:
                opts = opts.copy()
                fields = list(opts.get('fields', []))
                fields = [f for f in fields if f not in ('enable_background_jobs', 'jobs_status_control', 'enable_email_backup', 'email_backup_status_control')]
                opts['fields'] = tuple(fields)
                new_fieldsets.append((name, opts))
            return tuple(new_fieldsets)
        return fieldsets

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            return [f for f in list_display if f not in ('enable_background_jobs', 'enable_email_backup')]
        return list_display

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('toggle-jobs/', self.admin_site.admin_view(self.toggle_jobs_view), name='common_sitesettings_toggle_jobs'),
            path('toggle-email-backup/', self.admin_site.admin_view(self.toggle_email_backup_view), name='common_sitesettings_toggle_email_backup'),
            path('trigger-backup/', self.admin_site.admin_view(self.trigger_backup_view), name='common_sitesettings_trigger_backup'),
            path('reconcile-refunds/', self.admin_site.admin_view(self.reconcile_refunds_view), name='common_sitesettings_reconcile_refunds'),
        ]
        return custom_urls + urls

    def toggle_jobs_view(self, request):
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            messages.error(request, "🔐 Permission Denied: Staff/regular users cannot toggle background jobs.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))
        obj = SiteSettings.get_singleton()
        obj.enable_background_jobs = not obj.enable_background_jobs
        obj.save(update_fields=['enable_background_jobs'])
        status = "ENABLED" if obj.enable_background_jobs else "DISABLED"
        messages.success(request, f"Background jobs have been successfully {status}!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))

    def toggle_email_backup_view(self, request):
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            messages.error(request, "🔐 Permission Denied: Staff/regular users cannot toggle email backups.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))
        obj = SiteSettings.get_singleton()
        obj.enable_email_backup = not obj.enable_email_backup
        obj.save(update_fields=['enable_email_backup'])
        status = "ENABLED" if obj.enable_email_backup else "DISABLED"
        messages.success(request, f"Daily Database Email Backups have been successfully {status}!")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))

    def trigger_backup_view(self, request):
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            messages.error(request, "🔐 Permission Denied: Staff/regular users cannot trigger database backups.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))
        
        import subprocess
        try:
            # Execute the backup shell script (it runs mysqldump and triggers send_backup_email.py)
            result = subprocess.run(['/root/backup_db.sh'], capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                messages.success(request, "🎉 Database backup successfully created and sent to your email!")
            else:
                messages.error(request, f"❌ Backup script completed with error: {result.stderr or result.stdout}")
        except Exception as e:
            messages.error(request, f"❌ Failed to execute backup script: {e}")
            
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))

    def reconcile_refunds_view(self, request):
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            messages.error(request, "🔐 Permission Denied: Staff/regular users cannot run refund reconciliation.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))
            
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        try:
            call_command('reconcile_refunds', stdout=out)
            output = out.getvalue()
            lines = [line.strip() for line in output.split('\n') if line.strip() and not line.startswith('=')]
            summary = ", ".join(lines) if lines else "Done."
            messages.success(request, f"🔄 Refund reconciliation completed successfully! Details: {summary}")
        except Exception as e:
            messages.error(request, f"❌ Error running reconciliation: {e}")
            
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('admin:common_sitesettings_changelist')))

    def jobs_status_control(self, obj):
        status_label = "🟢 Running" if obj.enable_background_jobs else "🔴 Stopped"
        btn_text = "Stop Jobs" if obj.enable_background_jobs else "Start Jobs"
        btn_color = "#dc2626" if obj.enable_background_jobs else "#16a34a"
        url = reverse('admin:common_sitesettings_toggle_jobs')
        reconcile_url = reverse('admin:common_sitesettings_reconcile_refunds')
        
        return format_html(
            '<div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; max-width: 450px;">'
            '  <div style="font-size: 14px; margin-bottom: 12px; color: #1e293b;">Current Status: <strong style="font-size: 15px;">{}</strong></div>'
            '  <div style="display: flex; gap: 10px;">'
            '    <a href="{}" class="button" style="background: {}; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;">{}</a>'
            '    <a href="{}" class="button" style="background: #2563eb; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;">🔄 Reconcile Refunds</a>'
            '  </div>'
            '</div>',
            status_label, url, btn_color, btn_text, reconcile_url
        )
    jobs_status_control.short_description = "Background Jobs Control Dashboard"

    def email_backup_status_control(self, obj):
        status_label = "🟢 Enabled" if obj.enable_email_backup else "🔴 Disabled"
        btn_text = "Disable Email Backups" if obj.enable_email_backup else "Enable Email Backups"
        btn_color = "#dc2626" if obj.enable_email_backup else "#16a34a"
        url = reverse('admin:common_sitesettings_toggle_email_backup')
        backup_url = reverse('admin:common_sitesettings_trigger_backup')
        
        return format_html(
            '<div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; max-width: 450px;">'
            '  <div style="font-size: 14px; margin-bottom: 12px; color: #1e293b;">Email Backup Status: <strong style="font-size: 15px;">{}</strong></div>'
            '  <div style="display: flex; gap: 10px;">'
            '    <a href="{}" class="button" style="background: {}; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;">{}</a>'
            '    <a href="{}" class="button" style="background: #2563eb; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;">📧 Backup & Email Now</a>'
            '  </div>'
            '</div>',
            status_label, url, btn_color, btn_text, backup_url
        )
    email_backup_status_control.short_description = "Daily Email Backup Toggle Dashboard"


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'updated_at')
    search_fields = ('name', 'subject', 'body')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(SupportEnquiry)
class SupportEnquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('name', 'phone', 'message', 'resolved_notes')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('📞 Contact & Enquiry Info', {
            'fields': ('name', 'phone', 'message', 'created_at')
        }),
        ('⚙️ Resolution Status', {
            'fields': ('is_resolved', 'resolved_notes', 'updated_at')
        }),
    )


# ==========================================
# 🎁 FESTIVE CAMPAIGN & LUCKY DRAW ADMIN
# ==========================================
class CampaignPrizeInline(admin.TabularInline):
    model = CampaignPrize
    extra = 3
    fields = ('rank', 'title', 'subtitle', 'approx_value', 'image', 'display_order')
    ordering = ('rank', 'display_order')


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'status_badge', 'is_active_toggle', 'date_window_display', 
        'progress_meter', 'prizes_count', 'lucky_draw_btn'
    )
    list_filter = ('is_active', 'status', 'start_datetime', 'end_datetime')
    search_fields = ('title', 'slug', 'tagline', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CampaignPrizeInline]
    actions = ['activate_selected_campaigns', 'deactivate_selected_campaigns', 'run_lucky_draw_action']
    
    fieldsets = (
        ('🎉 Campaign Details', {
            'fields': ('title', 'slug', 'badge_text', 'tagline', 'description', 'theme_color')
        }),
        ('🖼️ Promotional Banners', {
            'fields': ('banner_image', 'mobile_banner'),
            'description': 'Upload celebratory banners shown on home & campaign landing pages.'
        }),
        ('⏰ Schedule & Target', {
            'fields': ('start_datetime', 'end_datetime', 'target_registrations', 'winner_announcement_date'),
            'description': 'Set the live contest period (e.g. 17 Oct 00:00 to 18 Oct 23:59) and target account goal.'
        }),
        ('⚙️ Display & Activation Controls', {
            'fields': ('is_active', 'status', 'show_on_homepage', 'show_on_register_page'),
            'description': 'Uncheck "Is Active" to immediately hide the campaign everywhere across the site.'
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:campaign_id>/run-lucky-draw/', self.admin_site.admin_view(self.run_lucky_draw_view), name='common_campaign_run_lucky_draw'),
        ]
        return custom_urls + urls

    def status_badge(self, obj):
        colors = {
            'active': '#16a34a',
            'upcoming': '#2563eb',
            'draft': '#64748b',
            'paused': '#d97706',
            'ended': '#dc2626',
            'winners_declared': '#9333ea',
        }
        color = colors.get(obj.status, '#64748b')
        live_dot = '🟢 Live Now' if obj.is_live else obj.get_status_display()
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 6px; font-weight: 700; font-size: 0.78rem;">{}</span>',
            color, live_dot
        )
    status_badge.short_description = "Status"

    def is_active_toggle(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #16a34a; font-weight: 800;">✔ Active</span>')
        return format_html('<span style="color: #dc2626; font-weight: 800;">✖ Off (Disabled)</span>')
    is_active_toggle.short_description = "On/Off Switch"

    def date_window_display(self, obj):
        s = obj.start_datetime.strftime('%d %b %H:%M')
        e = obj.end_datetime.strftime('%d %b %H:%M')
        return f"{s} → {e}"
    date_window_display.short_description = "Contest Dates"

    def progress_meter(self, obj):
        count = obj.participants_count
        target = obj.target_registrations
        pct = obj.progress_percentage
        bar_color = '#16a34a' if count >= target else '#2563eb'
        return format_html(
            '<div style="min-width: 140px;">'
            '  <div style="font-size: 0.8rem; font-weight: 700; margin-bottom: 2px;">{}/{} ({:.1f}%)</div>'
            '  <div style="background: #e2e8f0; height: 8px; border-radius: 4px; overflow: hidden;">'
            '    <div style="background: {}; width: {}%; height: 100%;"></div>'
            '  </div>'
            '</div>',
            count, target, pct, bar_color, min(pct, 100)
        )
    progress_meter.short_description = "Registrations"

    def prizes_count(self, obj):
        return obj.prizes.count()
    prizes_count.short_description = "Prizes"

    def lucky_draw_btn(self, obj):
        url = reverse('admin:common_campaign_run_lucky_draw', args=[obj.pk])
        if obj.status == 'winners_declared':
            return format_html(
                '<a href="{}" class="button" style="background: #9333ea; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-size: 0.75rem; font-weight: 700;">🏆 View Winners</a>',
                url
            )
        return format_html(
            '<a href="{}" class="button" style="background: #e11d48; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none; font-size: 0.75rem; font-weight: 700;">🎲 Lucky Draw</a>',
            url
        )
    lucky_draw_btn.short_description = "Lucky Draw"

    def run_lucky_draw_view(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, pk=campaign_id)
        prizes = campaign.prizes.all().order_by('rank', 'display_order')
        existing_winners = campaign.winners.select_related('prize', 'user', 'participant').all()

        if request.method == 'POST' and 'execute_draw' in request.POST:
            if not prizes.exists():
                messages.error(request, "Cannot run Lucky Draw: No prizes configured for this campaign. Please add prizes first.")
                return redirect('admin:common_campaign_change', campaign_id)

            # Candidate pool: eligible active users who haven't won a prize in this campaign yet
            eligible_participants = list(
                campaign.participants.filter(
                    is_eligible=True,
                    is_deleted=False,
                    user__is_active=True
                ).exclude(
                    user__in=existing_winners.values_list('user_id', flat=True)
                ).select_related('user')
            )

            if len(eligible_participants) < prizes.count():
                messages.error(
                    request, 
                    f"Not enough eligible participants ({len(eligible_participants)}) for {prizes.count()} configured prizes."
                )
                return HttpResponseRedirect(request.path)

            # Use cryptographically secure shuffle
            rng = secrets.SystemRandom()
            rng.shuffle(eligible_participants)

            created_winners = []
            for idx, prize in enumerate(prizes):
                if idx < len(eligible_participants):
                    participant = eligible_participants[idx]
                    winner = CampaignWinner.objects.create(
                        campaign=campaign,
                        prize=prize,
                        participant=participant,
                        user=participant.user,
                        ticket_number=participant.ticket_number,
                        is_published=True,
                        created_by=request.user
                    )
                    participant.is_winner = True
                    participant.save()
                    created_winners.append(winner)

            campaign.status = 'winners_declared'
            campaign.save()

            messages.success(
                request, 
                f"🎉 Lucky Draw successfully executed! Selected {len(created_winners)} winners for '{campaign.title}'."
            )
            return HttpResponseRedirect(request.path)

        context = {
            **self.admin_site.each_context(request),
            'campaign': campaign,
            'prizes': prizes,
            'existing_winners': existing_winners,
            'eligible_count': campaign.participants.filter(is_eligible=True, is_deleted=False, user__is_active=True).count(),
            'title': f"Lucky Draw Engine: {campaign.title}",
        }
        return render(request, 'admin/common/campaign_lucky_draw.html', context)

    def activate_selected_campaigns(self, request, queryset):
        count = queryset.update(is_active=True, status='active')
        messages.success(request, f"Activated {count} campaign(s).")
    activate_selected_campaigns.short_description = "🟢 Activate Selected Campaigns"

    def deactivate_selected_campaigns(self, request, queryset):
        count = queryset.update(is_active=False)
        messages.success(request, f"Deactivated {count} campaign(s). They are now completely hidden on the site.")
    deactivate_selected_campaigns.short_description = "🛑 Deactivate (Turn Off) Selected Campaigns"


@admin.register(CampaignParticipant)
class CampaignParticipantAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'user_info', 'campaign', 'is_eligible', 'is_winner', 'created_at')
    list_filter = ('campaign', 'is_eligible', 'is_winner', 'created_at')
    search_fields = ('ticket_number', 'user__phone', 'user__email', 'user__full_name')
    readonly_fields = ('created_at', 'updated_at', 'ticket_number')

    def user_info(self, obj):
        name = obj.user.full_name or "Anonymous"
        return f"{name} ({obj.user.phone or obj.user.email})"
    user_info.short_description = "Participant User"


@admin.register(CampaignWinner)
class CampaignWinnerAdmin(admin.ModelAdmin):
    list_display = ('rank_badge', 'prize_title', 'winner_info', 'ticket_number', 'campaign', 'is_published', 'created_at')
    list_filter = ('campaign', 'prize__rank', 'is_published', 'created_at')
    search_fields = ('ticket_number', 'user__phone', 'user__email', 'user__full_name', 'prize__title')
    actions = ['publish_winners', 'unpublish_winners']

    def rank_badge(self, obj):
        ranks = {1: ('🥇 1st Prize', '#f59e0b'), 2: ('🥈 2nd Prize', '#94a3b8'), 3: ('🥉 3rd Prize', '#b45309')}
        label, color = ranks.get(obj.prize.rank, (f"Rank #{obj.prize.rank}", '#64748b'))
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 700;">{}</span>',
            color, label
        )
    rank_badge.short_description = "Rank"

    def prize_title(self, obj):
        return obj.prize.title
    prize_title.short_description = "Prize Won"

    def winner_info(self, obj):
        name = obj.user.full_name or "Anonymous"
        return f"{name} ({obj.user.phone or obj.user.email})"
    winner_info.short_description = "Winner"

    def publish_winners(self, request, queryset):
        queryset.update(is_published=True)
        messages.success(request, "Selected winners are now published publicly on the website.")
    publish_winners.short_description = "📢 Publish Selected Winners"

    def unpublish_winners(self, request, queryset):
        queryset.update(is_published=False)
        messages.success(request, "Selected winners are now hidden from the public website.")
    unpublish_winners.short_description = "🔒 Hide Selected Winners"