from django.contrib import admin

from .models import (
    ApprovalFlow,
    ApprovalRequest,
    AuditLog,
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    CompetitionRuleSet,
    Contract,
    ExternalSystem,
    IntegrationRecord,
    Match,
    MatchEvent,
    MatchLineup,
    Negotiation,
    Notification,
    Person,
    Proposal,
    TeamCategory,
    Tenant,
    TenantMembership,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'active', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('active',)


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'role', 'active', 'created_at')
    search_fields = ('user__username', 'user__email', 'tenant__name')
    list_filter = ('role', 'active')


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'tenant', 'city', 'state', 'active')
    search_fields = ('name', 'slug', 'city')
    list_filter = ('active', 'state')


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'kind', 'tenant', 'active')
    search_fields = ('full_name', 'document_id')
    list_filter = ('kind', 'active')


@admin.register(TeamCategory)
class TeamCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'club', 'tenant', 'age_min', 'age_max', 'active')
    search_fields = ('name', 'club__name')
    list_filter = ('active',)


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'tenant', 'scope', 'active')
    search_fields = ('name', 'slug')
    list_filter = ('scope', 'active')


@admin.register(CompetitionRuleSet)
class CompetitionRuleSetAdmin(admin.ModelAdmin):
    list_display = ('competition', 'min_registration_notice_hours', 'red_card_suspension_matches', 'immutability_window_hours', 'conflict_policy')
    list_filter = ('active', 'conflict_policy')


@admin.register(CompetitionEdition)
class CompetitionEditionAdmin(admin.ModelAdmin):
    list_display = ('competition', 'name', 'season_year', 'status', 'registration_deadline')
    search_fields = ('name', 'competition__name', 'slug')
    list_filter = ('status', 'season_year')


@admin.register(CompetitionPhase)
class CompetitionPhaseAdmin(admin.ModelAdmin):
    list_display = ('edition', 'code', 'name', 'order', 'status')
    search_fields = ('code', 'name')
    list_filter = ('status',)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('reference_code', 'phase', 'home_club', 'away_club', 'scheduled_at', 'status')
    search_fields = ('reference_code', 'home_club__name', 'away_club__name')
    list_filter = ('status',)


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = ('match', 'event_type', 'minute', 'player')
    list_filter = ('event_type',)


@admin.register(MatchLineup)
class MatchLineupAdmin(admin.ModelAdmin):
    list_display = ('match', 'club', 'player', 'jersey_number', 'is_starter', 'captain')
    list_filter = ('is_starter', 'captain')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('person', 'club', 'tenant', 'status', 'start_date', 'end_date')
    search_fields = ('person__full_name', 'club__name')
    list_filter = ('status',)


@admin.register(Negotiation)
class NegotiationAdmin(admin.ModelAdmin):
    list_display = ('person', 'club', 'tenant', 'status', 'opened_at')
    list_filter = ('status',)


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ('negotiation', 'club', 'amount', 'currency', 'status')
    list_filter = ('status', 'currency')


@admin.register(ApprovalFlow)
class ApprovalFlowAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'tenant', 'target_model', 'active')
    search_fields = ('name', 'code', 'target_model')


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('flow', 'requested_by', 'status', 'target_model', 'target_object_id')
    list_filter = ('status',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('subject', 'recipient', 'tenant', 'channel', 'status', 'sent_at')
    list_filter = ('channel', 'status')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'tenant', 'actor', 'action', 'content_type', 'object_id')
    list_filter = ('action', 'content_type')
    search_fields = ('object_id', 'correlation_id')
    readonly_fields = ('occurred_at',)


@admin.register(ExternalSystem)
class ExternalSystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'tenant', 'base_url', 'active')
    list_filter = ('kind', 'active')


@admin.register(IntegrationRecord)
class IntegrationRecordAdmin(admin.ModelAdmin):
    list_display = ('external_system', 'correlation_id', 'status', 'received_at', 'processed_at')
    search_fields = ('correlation_id', 'external_object_id')
    list_filter = ('status',)
