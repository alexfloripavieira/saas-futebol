"""Catálogo de módulos contratáveis e navegação orientada por módulo.

Cada item de menu pertence a um módulo. O menu lateral e o gating de acesso
derivam de quais módulos o tenant contratou (``TenantModuleSubscription``).

Regra de compatibilidade: um tenant **sem nenhuma** assinatura de módulo é
considerado não-provisionado e enxerga o catálogo completo (comportamento
legado / administração). Assim que ao menos uma assinatura existe, apenas os
módulos habilitados aparecem e são acessíveis.
"""

from __future__ import annotations

# Catálogo canônico de módulos. ``code`` é a chave persistida em
# ``TenantModuleSubscription.module_code``; ``name`` é o rótulo padrão.
MODULE_CATALOG = (
    {'code': 'operacao', 'name': 'Operação', 'icon': '🏁', 'category': 'Base esportiva', 'description': 'Clubes, pessoas, competições, partidas, escalações e rotina esportiva.'},
    {'code': 'aprovacoes', 'name': 'Aprovações', 'icon': '✅', 'category': 'Governança', 'description': 'Fluxos, solicitações, notificações e decisões com responsáveis definidos.'},
    {'code': 'transferencias', 'name': 'Transferências', 'icon': '↔️', 'category': 'Mercado', 'description': 'Contratos, negociações, propostas e evidências em uma central única.'},
    {'code': 'ia', 'name': 'IA', 'icon': '🧠', 'category': 'Inteligência', 'description': 'Treinador Inteligente, providers, agentes, fontes esportivas e conhecimento.'},
    {'code': 'relatorios', 'name': 'Relatórios', 'icon': '📊', 'category': 'Visibilidade', 'description': 'Indicadores operacionais, BI e leitura executiva do desempenho.'},
    {'code': 'previsoes', 'name': 'Previsões', 'icon': '🔮', 'category': 'Antecipação', 'description': 'Cenários inteligentes para apoiar decisões esportivas e administrativas.'},
    {'code': 'integracoes', 'name': 'Integrações', 'icon': '🔗', 'category': 'Conectividade', 'description': 'Troca controlada de dados com sistemas e provedores externos.'},
    {'code': 'auditoria', 'name': 'Auditoria', 'icon': '🕵️', 'category': 'Conformidade', 'description': 'Trilha imutável das ações importantes e rastreabilidade por tenant.'},
    {'code': 'automacoes', 'name': 'Automações', 'icon': '⚙️', 'category': 'Escala', 'description': 'Rotinas repetíveis e monitoradas para a operação ganhar velocidade.'},
)

MODULE_CODES = tuple(module['code'] for module in MODULE_CATALOG)
MODULE_NAMES = {module['code']: module['name'] for module in MODULE_CATALOG}

# Módulo base sempre disponível (dashboard e cadastros essenciais). Não pode
# ser ocultado nem bloqueado, garantindo que todo tenant tenha um ponto de
# entrada operacional.
BASE_MODULE = 'operacao'

# Estrutura de navegação: grupos de menu vinculados a um módulo. Cada item
# aponta para uma ``url_name`` resolvida no template.
NAV_GROUPS = (
    {
        'module': 'operacao',
        'label': 'Operação',
        'icon': '🏁',
        'open': True,
        'items': (
            {'label': 'Dashboard', 'url_name': 'home', 'icon': '🏠'},
            {'label': 'Clubes', 'url_name': 'club-list', 'icon': '⚽'},
            {'label': 'Pessoas', 'url_name': 'person-list', 'icon': '👥'},
            {'label': 'Competições', 'url_name': 'competition-list', 'icon': '🏆'},
            {'label': 'Partidas', 'url_name': 'match-list', 'icon': '📅'},
        ),
    },
    {
        'module': 'aprovacoes',
        'label': 'Aprovações',
        'icon': '✅',
        'open': True,
        'items': (
            {'label': 'Fluxos', 'url_name': 'approval-flow-list', 'icon': '🧭'},
            {'label': 'Solicitações', 'url_name': 'approval-request-list', 'icon': '📝'},
            {'label': 'Notificações', 'url_name': 'notification-list', 'icon': '🔔'},
        ),
    },
    {
        'module': 'transferencias',
        'label': 'Transferências',
        'icon': '↔️',
        'open': False,
        'items': (
            {'label': 'Central de transferências', 'url_name': 'transfer-center', 'icon': '↔️'},
            {'label': 'Contratos', 'url_name': 'contract-list', 'icon': '📄'},
            {'label': 'Negociações', 'url_name': 'negotiation-list', 'icon': '🤝'},
            {'label': 'Propostas', 'url_name': 'proposal-list', 'icon': '💬'},
        ),
    },
    {
        'module': 'ia',
        'label': 'Inteligência esportiva',
        'icon': '🧠',
        'open': True,
        'items': (
            {'label': 'Treinador Inteligente', 'url_name': 'intelligent-coach-center', 'icon': '🧑‍🏫'},
            {'label': 'Cobertura dos dados', 'url_name': 'sports-data-source-list', 'icon': '📡'},
            {'label': 'Laboratório de IA', 'url_name': 'ai-center', 'icon': '✨'},
            {'label': 'Configuração · Providers', 'url_name': 'ai-provider-list', 'icon': '🔌'},
            {'label': 'Configuração · Agentes', 'url_name': 'ai-agent-list', 'icon': '🤖'},
            {'label': 'Configuração · Conhecimento', 'url_name': 'knowledge-source-list', 'icon': '📚'},
        ),
    },
    {
        'module': 'relatorios',
        'label': 'Relatórios',
        'icon': '📊',
        'open': False,
        'items': (
            {'label': 'Relatórios', 'url_name': 'report-center', 'icon': '📈'},
            {'label': 'BI', 'url_name': 'bi-center', 'icon': '📊'},
        ),
    },
    {
        'module': 'previsoes',
        'label': 'Previsões',
        'icon': '🔮',
        'open': False,
        'items': (
            {'label': 'Previsões inteligentes', 'url_name': 'prediction-center', 'icon': '🔮'},
        ),
    },
    {
        'module': 'integracoes',
        'label': 'Integrações',
        'icon': '🔗',
        'open': False,
        'items': (
            {'label': 'Integrações', 'url_name': 'integration-hub', 'icon': '🔗'},
        ),
    },
    {
        'module': 'auditoria',
        'label': 'Auditoria',
        'icon': '🕵️',
        'open': False,
        'items': (
            {'label': 'Auditoria', 'url_name': 'audit-log-list', 'icon': '🕵️'},
        ),
    },
    {
        'module': 'automacoes',
        'label': 'Automações',
        'icon': '⚙️',
        'open': False,
        'items': (
            {'label': 'Automações', 'url_name': 'automation-center', 'icon': '⚙️'},
        ),
    },
)

# Grupo institucional sempre presente (fora do gating de módulos).
ACCOUNT_GROUP = {
    'label': 'Conta',
    'icon': '👤',
    'open': False,
    'items': (
        {'label': 'Administração do tenant', 'url_name': 'tenant-admin', 'icon': '🏛️'},
        {'label': 'Logout', 'url_name': 'logout', 'icon': '🚪'},
        {'label': 'Admin', 'url_name': 'admin:index', 'icon': '🛠️'},
    ),
}


def enabled_module_codes(tenant):
    """Conjunto de códigos de módulo habilitados para o tenant.

    Retorna ``None`` quando o tenant não possui nenhuma assinatura (não
    provisionado) — o chamador deve interpretar como "todos os módulos".
    """
    if tenant is None:
        return set(MODULE_CODES)
    subscriptions = tenant.tenantmodulesubscriptions.all()
    codes = {sub.module_code for sub in subscriptions}
    if not codes:
        return None
    enabled = {sub.module_code for sub in subscriptions if sub.enabled}
    enabled.add(BASE_MODULE)  # o módulo base nunca é ocultado
    return enabled


def tenant_has_module(tenant, code):
    """True se o módulo está contratado (ou o tenant não foi provisionado)."""
    if code == BASE_MODULE:
        return True
    enabled = enabled_module_codes(tenant)
    if enabled is None:
        return True
    return code in enabled


def build_nav_groups(enabled):
    """Filtra ``NAV_GROUPS`` pelos módulos habilitados.

    ``enabled`` é um conjunto de códigos ou ``None`` (mostra tudo).
    """
    # ``enabled_module_codes`` já injeta ``BASE_MODULE`` no conjunto; quando
    # ``enabled`` é ``None`` (tenant não provisionado) exibimos tudo.
    return [group for group in NAV_GROUPS if enabled is None or group['module'] in enabled]
