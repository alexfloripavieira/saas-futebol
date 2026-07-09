from django.contrib import admin

from .models import (
    AIAgent,
    AIAgentSourceLink,
    AIProvider,
    ApprovalDecision,
    ApprovalFlow,
    ApprovalFlowStep,
    ApprovalRequest,
    AuditLog,
    Club,
    Competition,
    CompetitionEdition,
    CompetitionPhase,
    CompetitionRuleSet,
    Contract,
    Evidence,
    ExternalSystem,
    IntegrationRecord,
    KnowledgeSource,
    Match,
    MatchEvent,
    MatchLineup,
    Negotiation,
    Notification,
    Person,
    Proposal,
    TeamCategory,
    Tenant,
    TenantBranding,
    TenantMembership,
    TenantModuleSubscription,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'active', 'has_public_api_key', 'created_at')
    search_fields = ('name', 'slug')
    list_filter = ('active',)
    actions = ('gerar_chave_api_publica',)

    @admin.display(boolean=True, description='Chave API pública')
    def has_public_api_key(self, obj):
        return bool(obj.public_api_key)

    @admin.action(description='Gerar/rotacionar chave da API pública')
    def gerar_chave_api_publica(self, request, queryset):
        for tenant in queryset:
            tenant.rotate_public_api_key()
        self.message_user(request, f'Chave da API pública gerada para {queryset.count()} tenant(s).')


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'role', 'active', 'created_at')
    search_fields = ('user__username', 'user__email', 'tenant__name')
    list_filter = ('role', 'active')


@admin.register(TenantBranding)
class TenantBrandingAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'public_title', 'primary_color', 'accent_color', 'updated_at')
    search_fields = ('tenant__name', 'public_title')


@admin.register(TenantModuleSubscription)
class TenantModuleSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('module_name', 'module_code', 'tenant', 'enabled', 'plan_name')
    search_fields = ('module_name', 'module_code', 'tenant__name', 'plan_name')
    list_filter = ('enabled', 'module_code')


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


class ApprovalFlowStepInline(admin.TabularInline):
    model = ApprovalFlowStep
    extra = 1


@admin.register(ApprovalFlow)
class ApprovalFlowAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'tenant', 'target_kind', 'active')
    search_fields = ('name', 'code')
    list_filter = ('target_kind', 'active')
    inlines = [ApprovalFlowStepInline]


@admin.register(ApprovalFlowStep)
class ApprovalFlowStepAdmin(admin.ModelAdmin):
    list_display = ('flow', 'order', 'required_role', 'requires_evidence', 'tenant')
    list_filter = ('required_role', 'requires_evidence')


class ApprovalDecisionInline(admin.TabularInline):
    model = ApprovalDecision
    extra = 0


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('flow', 'requested_by', 'status', 'content_type', 'object_id', 'requested_at')
    list_filter = ('status', 'content_type')
    inlines = [ApprovalDecisionInline]


@admin.register(ApprovalDecision)
class ApprovalDecisionAdmin(admin.ModelAdmin):
    list_display = ('request', 'step', 'decided_by', 'outcome', 'decided_at')
    list_filter = ('outcome',)


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'object_id', 'uploaded_by', 'tenant', 'created_at')
    list_filter = ('content_type',)
    search_fields = ('object_id', 'note')


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


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'model_name', 'tenant', 'active')
    list_filter = ('kind', 'active')
    search_fields = ('name', 'model_name', 'notes')


@admin.register(KnowledgeSource)
class KnowledgeSourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'tenant', 'identifier', 'source_url', 'active')
    list_filter = ('kind', 'active')
    search_fields = ('title', 'identifier', 'source_path', 'source_url', 'summary')


@admin.register(AIAgent)
class AIAgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'provider', 'tenant', 'active')
    list_filter = ('active', 'provider')
    search_fields = ('name', 'slug', 'purpose', 'system_prompt')
    filter_horizontal = ('knowledge_sources',)


@admin.register(AIAgentSourceLink)
class AIAgentSourceLinkAdmin(admin.ModelAdmin):
    list_display = ('agent', 'source', 'tenant', 'order', 'active')
    list_filter = ('active',)


@admin.register(ExternalSystem)
class ExternalSystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'tenant', 'base_url', 'active')
    list_filter = ('kind', 'active')


@admin.register(IntegrationRecord)
class IntegrationRecordAdmin(admin.ModelAdmin):
    list_display = ('external_system', 'correlation_id', 'status', 'received_at', 'processed_at')
    search_fields = ('correlation_id', 'external_object_id')
    list_filter = ('status',)
