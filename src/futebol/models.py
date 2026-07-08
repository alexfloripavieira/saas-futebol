from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Tenant(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TenantMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN_TENANT = 'admin_tenant', 'Administrador do tenant'
        GESTOR_CLUBE = 'gestor_clube', 'Gestor do clube'
        GESTOR_COMPETICAO = 'gestor_competicao', 'Gestor da competição'
        APROVADOR = 'aprovador', 'Aprovador'
        DELEGADO_PARTIDA = 'delegado_partida', 'Delegado da partida'
        AUDITOR = 'auditor_somente_leitura', 'Auditor somente leitura'
        ADMIN_PLATAFORMA = 'admin_plataforma', 'Administrador da plataforma'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_memberships')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=32, choices=Role.choices)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'tenant', 'role')]
        ordering = ['tenant__name', 'user__username']

    def __str__(self):
        return f'{self.user} — {self.tenant} — {self.get_role_display()}'


class TenantScopedModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='%(class)ss')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    tenant_bound_fields = ()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        errors = {}
        for field_name in self.tenant_bound_fields:
            related = getattr(self, field_name, None)
            related_tenant_id = getattr(related, 'tenant_id', None)
            if related is not None and related_tenant_id is not None and self.tenant_id is not None and related_tenant_id != self.tenant_id:
                errors[field_name] = 'O vínculo precisa pertencer ao mesmo tenant.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Club(TenantScopedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160)
    registration_code = models.CharField(max_length=64, blank=True, default='')
    city = models.CharField(max_length=120, blank=True, default='')
    state = models.CharField(max_length=2, blank=True, default='')
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'slug'], name='uniq_club_slug_per_tenant'),
            models.UniqueConstraint(fields=['tenant', 'name'], name='uniq_club_name_per_tenant'),
        ]

    def __str__(self):
        return self.name


class Person(TenantScopedModel):
    class Kind(models.TextChoices):
        ATHLETE = 'athlete', 'Atleta'
        COACH = 'coach', 'Técnico'
        STAFF = 'staff', 'Comissão'
        REFEREE = 'referee', 'Arbitragem'
        OTHER = 'other', 'Outro'

    full_name = models.CharField(max_length=160)
    document_id = models.CharField(max_length=32, blank=True, default='')
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.ATHLETE)
    birth_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['full_name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'full_name'], name='uniq_person_name_per_tenant'),
        ]

    def __str__(self):
        return self.full_name


class TeamCategory(TenantScopedModel):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=120)
    age_min = models.PositiveSmallIntegerField(default=0)
    age_max = models.PositiveSmallIntegerField(default=99)
    active = models.BooleanField(default=True)

    tenant_bound_fields = ('club',)

    class Meta:
        ordering = ['club__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'club', 'name'], name='uniq_category_per_club'),
            models.CheckConstraint(check=Q(age_min__lte=models.F('age_max')), name='category_age_range_valid'),
        ]

    def __str__(self):
        return f'{self.club} — {self.name}'


class Competition(TenantScopedModel):
    class Scope(models.TextChoices):
        LEAGUE = 'league', 'Liga'
        CUP = 'cup', 'Copa'
        CHAMPIONSHIP = 'championship', 'Campeonato'
        TOURNAMENT = 'tournament', 'Torneio'

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160)
    scope = models.CharField(max_length=24, choices=Scope.choices, default=Scope.CHAMPIONSHIP)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'slug'], name='uniq_competition_slug_per_tenant'),
            models.UniqueConstraint(fields=['tenant', 'name'], name='uniq_competition_name_per_tenant'),
        ]

    def __str__(self):
        return self.name


class CompetitionRuleSet(TenantScopedModel):
    class ConflictPolicy(models.TextChoices):
        SKIP = 'skip', 'Pular'
        OVERWRITE = 'overwrite', 'Sobrescrever'
        ERROR = 'error', 'Erro'

    competition = models.OneToOneField(Competition, on_delete=models.CASCADE, related_name='ruleset')
    min_registration_notice_hours = models.PositiveSmallIntegerField(default=24)
    red_card_suspension_matches = models.PositiveSmallIntegerField(default=1)
    publish_quorum_percent = models.PositiveSmallIntegerField(default=60)
    immutability_window_hours = models.PositiveSmallIntegerField(default=24)
    import_export_max_mb = models.PositiveSmallIntegerField(default=10)
    import_export_max_rows = models.PositiveIntegerField(default=5000)
    conflict_policy = models.CharField(max_length=16, choices=ConflictPolicy.choices, default=ConflictPolicy.SKIP)
    active = models.BooleanField(default=True)

    tenant_bound_fields = ('competition',)

    class Meta:
        ordering = ['competition__name']

    def __str__(self):
        return f'Regras — {self.competition.name}'


class CompetitionEdition(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        OPEN = 'open', 'Aberta'
        LOCKED = 'locked', 'Bloqueada'
        RUNNING = 'running', 'Em andamento'
        FINISHED = 'finished', 'Encerrada'
        ARCHIVED = 'archived', 'Arquivada'

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='editions')
    slug = models.SlugField(max_length=160)
    name = models.CharField(max_length=160)
    season_year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    tenant_bound_fields = ('competition',)

    class Meta:
        ordering = ['-season_year', 'competition__name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'competition', 'slug'], name='uniq_edition_slug_per_competition'),
            models.UniqueConstraint(fields=['tenant', 'competition', 'season_year'], name='uniq_edition_season_per_competition'),
        ]

    def __str__(self):
        return f'{self.competition.name} {self.season_year}'


class CompetitionPhase(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        SCHEDULED = 'scheduled', 'Agendada'
        ACTIVE = 'active', 'Ativa'
        CLOSED = 'closed', 'Encerrada'

    edition = models.ForeignKey(CompetitionEdition, on_delete=models.CASCADE, related_name='phases')
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    order = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    tenant_bound_fields = ('edition',)

    class Meta:
        ordering = ['edition__competition__name', 'edition__season_year', 'order']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'edition', 'code'], name='uniq_phase_code_per_edition'),
            models.UniqueConstraint(fields=['tenant', 'edition', 'order'], name='uniq_phase_order_per_edition'),
        ]

    def __str__(self):
        return f'{self.edition} — {self.name}'


class Match(TenantScopedModel):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Agendada'
        CONFIRMED = 'confirmed', 'Confirmada'
        PLAYED = 'played', 'Disputada'
        CANCELLED = 'cancelled', 'Cancelada'
        POSTPONED = 'postponed', 'Adiada'

    phase = models.ForeignKey(CompetitionPhase, on_delete=models.CASCADE, related_name='matches')
    home_club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name='home_matches')
    away_club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name='away_matches')
    reference_code = models.CharField(max_length=64)
    scheduled_at = models.DateTimeField()
    venue = models.CharField(max_length=160, blank=True, default='')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    immutable_after = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    tenant_bound_fields = ('phase', 'home_club', 'away_club')

    class Meta:
        ordering = ['-scheduled_at']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'reference_code'], name='uniq_match_ref_per_tenant'),
            models.UniqueConstraint(fields=['tenant', 'phase', 'scheduled_at', 'home_club', 'away_club'], name='uniq_match_slot_per_tenant'),
            models.CheckConstraint(check=~Q(home_club=models.F('away_club')), name='match_home_away_distinct'),
        ]

    def clean(self):
        super().clean()
        if self.home_club_id and self.away_club_id and self.home_club_id == self.away_club_id:
            raise ValidationError({'away_club': 'Mandante e visitante precisam ser clubes diferentes.'})
        if self.immutable_after is None and self.scheduled_at and self.phase_id:
            ruleset = CompetitionRuleSet.objects.filter(competition=self.phase.edition.competition).first()
            window = ruleset.immutability_window_hours if ruleset else 24
            self.immutable_after = self.scheduled_at + timedelta(hours=window)

    def is_mutable(self, reference_time=None):
        reference_time = reference_time or timezone.now()
        if self.immutable_after is None:
            return True
        return reference_time < self.immutable_after

    def __str__(self):
        return f'{self.home_club} x {self.away_club} — {self.scheduled_at:%d/%m/%Y %H:%M}'


class MatchEvent(TenantScopedModel):
    class EventType(models.TextChoices):
        GOAL = 'goal', 'Gol'
        YELLOW_CARD = 'yellow_card', 'Cartão amarelo'
        RED_CARD = 'red_card', 'Cartão vermelho'
        SUBSTITUTION = 'substitution', 'Substituição'
        FOUL = 'foul', 'Falta'
        OTHER = 'other', 'Outro'

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='events')
    player = models.ForeignKey(Person, on_delete=models.PROTECT, null=True, blank=True, related_name='events')
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    minute = models.PositiveSmallIntegerField()
    period = models.CharField(max_length=32, blank=True, default='')
    details = models.JSONField(default=dict, blank=True)

    tenant_bound_fields = ('match', 'player')

    class Meta:
        ordering = ['minute', 'id']
        constraints = [
            models.CheckConstraint(check=Q(minute__gte=0), name='match_event_minute_non_negative'),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} — {self.match}'


class MatchLineup(TenantScopedModel):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='lineups')
    player = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='lineups')
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name='lineups')
    jersey_number = models.PositiveSmallIntegerField(null=True, blank=True)
    position = models.CharField(max_length=32, blank=True, default='')
    is_starter = models.BooleanField(default=True)
    captain = models.BooleanField(default=False)

    tenant_bound_fields = ('match', 'player', 'club')

    class Meta:
        ordering = ['match__scheduled_at', 'club__name', 'player__full_name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'match', 'player'], name='uniq_lineup_player_per_match'),
        ]

    def __str__(self):
        return f'{self.player} — {self.match}'


class Contract(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        ACTIVE = 'active', 'Ativo'
        SUSPENDED = 'suspended', 'Suspenso'
        TERMINATED = 'terminated', 'Encerrado'

    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name='contracts')
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name='contracts')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    termination_reason = models.TextField(blank=True, default='')

    tenant_bound_fields = ('person', 'club')

    class Meta:
        ordering = ['-start_date', 'person__full_name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'person', 'club'],
                condition=Q(status='active'),
                name='uniq_active_contract_per_pair',
            ),
        ]

    def clean(self):
        super().clean()
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'A data final precisa ser igual ou posterior ao início.'})

    def __str__(self):
        return f'{self.person} — {self.club}'


class Negotiation(TenantScopedModel):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberta'
        ACCEPTED = 'accepted', 'Aceita'
        REJECTED = 'rejected', 'Rejeitada'
        WITHDRAWN = 'withdrawn', 'Cancelada'

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='negotiations')
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='negotiations')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    tenant_bound_fields = ('club', 'person')

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f'{self.person} ↔ {self.club}'


class Proposal(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        SENT = 'sent', 'Enviada'
        ACCEPTED = 'accepted', 'Aceita'
        REJECTED = 'rejected', 'Rejeitada'

    negotiation = models.ForeignKey(Negotiation, on_delete=models.CASCADE, related_name='proposals')
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='proposals')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='BRL')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    sent_at = models.DateTimeField(null=True, blank=True)

    tenant_bound_fields = ('negotiation', 'club')

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f'{self.club} — {self.amount} {self.currency}'


class ApprovalFlow(TenantScopedModel):
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=120)
    target_model = models.CharField(max_length=120)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'code'], name='uniq_approval_flow_code_per_tenant'),
        ]

    def __str__(self):
        return self.name


class ApprovalRequest(TenantScopedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovada'
        REJECTED = 'rejected', 'Rejeitada'
        CANCELLED = 'cancelled', 'Cancelada'

    flow = models.ForeignKey(ApprovalFlow, on_delete=models.CASCADE, related_name='requests')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='approval_requests')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    target_model = models.CharField(max_length=120)
    target_object_id = models.CharField(max_length=64)
    reason = models.TextField(blank=True, default='')
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    tenant_bound_fields = ('flow',)

    class Meta:
        ordering = ['-requested_at']

    def clean(self):
        super().clean()
        errors = {}
        if not self.target_model:
            errors['target_model'] = 'Informe o modelo de destino.'
        if not self.target_object_id:
            errors['target_object_id'] = 'Informe o identificador do objeto de destino.'
        if self.tenant_id and self.requested_by_id and not self.requested_by.is_superuser:
            has_membership = TenantMembership.objects.filter(
                user=self.requested_by,
                tenant_id=self.tenant_id,
                active=True,
                tenant__active=True,
            ).exists()
            if not has_membership:
                errors['requested_by'] = 'O solicitante precisa ter vínculo ativo com o tenant.'
        if errors:
            raise ValidationError(errors)

    def decide(self, new_status, *, decided_at=None):
        if self.status != self.Status.PENDING:
            raise ValidationError('A solicitação já foi decidida.')
        if new_status not in {self.Status.APPROVED, self.Status.REJECTED, self.Status.CANCELLED}:
            raise ValidationError('Status de decisão inválido.')
        self.status = new_status
        self.decided_at = decided_at or timezone.now()
        self.save(update_fields=['status', 'decided_at'])
        return self

    def approve(self, *, decided_at=None):
        return self.decide(self.Status.APPROVED, decided_at=decided_at)

    def reject(self, *, decided_at=None):
        return self.decide(self.Status.REJECTED, decided_at=decided_at)

    def cancel(self, *, decided_at=None):
        return self.decide(self.Status.CANCELLED, decided_at=decided_at)

    def __str__(self):
        return f'{self.flow} — {self.status}'


class Notification(TenantScopedModel):
    class Channel(models.TextChoices):
        IN_APP = 'in_app', 'In-app'
        EMAIL = 'email', 'E-mail'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Na fila'
        SENT = 'sent', 'Enviada'
        FAILED = 'failed', 'Falhou'
        READ = 'read', 'Lida'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.IN_APP)
    subject = models.CharField(max_length=160)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    metadata = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-id']

    def clean(self):
        super().clean()
        if self.tenant_id and self.recipient_id and not self.recipient.is_superuser:
            has_membership = TenantMembership.objects.filter(
                user=self.recipient,
                tenant_id=self.tenant_id,
                active=True,
                tenant__active=True,
            ).exists()
            if not has_membership:
                raise ValidationError({'recipient': 'O destinatário precisa ter vínculo ativo com o tenant.'})

    def queue(self):
        self.status = self.Status.QUEUED
        self.sent_at = None
        self.save(update_fields=['status', 'sent_at'])
        return self

    def mark_sent(self, *, sent_at=None):
        self.status = self.Status.SENT
        self.sent_at = sent_at or timezone.now()
        self.save(update_fields=['status', 'sent_at'])
        return self

    def mark_failed(self):
        self.status = self.Status.FAILED
        self.save(update_fields=['status'])
        return self

    def mark_read(self):
        self.status = self.Status.READ
        self.save(update_fields=['status'])
        return self

    def __str__(self):
        return self.subject


class AuditLog(TenantScopedModel):
    class Action(models.TextChoices):
        CREATE = 'create', 'Criar'
        UPDATE = 'update', 'Atualizar'
        DELETE = 'delete', 'Excluir'
        APPROVE = 'approve', 'Aprovar'
        REJECT = 'reject', 'Rejeitar'
        IMPORT = 'import', 'Importar'
        EXPORT = 'export', 'Exportar'

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=16, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey('content_type', 'object_id')
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=80, blank=True, default='')
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('AuditLog é append-only e não pode ser atualizado.')
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('AuditLog é append-only e não pode ser excluído.')

    def __str__(self):
        return f'{self.get_action_display()} — {self.content_type}:{self.object_id}'


class ExternalSystem(TenantScopedModel):
    class Kind(models.TextChoices):
        PAYMENT = 'payment', 'Pagamento'
        EMAIL = 'email', 'E-mail'
        STORAGE = 'storage', 'Armazenamento'
        IMPORT = 'import', 'Importação'
        EXPORT = 'export', 'Exportação'
        OTHER = 'other', 'Outro'

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.OTHER)
    base_url = models.URLField(blank=True, default='')
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='uniq_external_system_name_per_tenant'),
        ]

    def __str__(self):
        return self.name


class IntegrationRecord(TenantScopedModel):
    external_system = models.ForeignKey(ExternalSystem, on_delete=models.CASCADE, related_name='integration_records')
    correlation_id = models.CharField(max_length=120)
    external_object_id = models.CharField(max_length=120, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, default='received')
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')

    tenant_bound_fields = ('external_system',)

    class Meta:
        ordering = ['-received_at']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'external_system', 'correlation_id'], name='uniq_integration_correlation_per_system'),
        ]

    def __str__(self):
        return f'{self.external_system} — {self.correlation_id}'
