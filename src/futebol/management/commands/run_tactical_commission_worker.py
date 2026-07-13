import logging
import os
import signal
import socket
import threading

from django.core.management.base import BaseCommand, CommandError

from futebol.services.tactical_commission import claim_next_task, execute_claimed_task


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Processa de forma durável a fila da Comissão Técnica Digital.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Processa no máximo uma tarefa disponível e encerra.',
        )
        parser.add_argument(
            '--poll-seconds',
            type=float,
            default=2.0,
            help='Intervalo entre consultas à fila quando ela estiver vazia.',
        )
        parser.add_argument(
            '--lease-seconds',
            type=int,
            default=360,
            help='Duração do lease exclusivo adquirido para cada tarefa.',
        )

    def handle(self, *args, **options):
        poll_seconds = options['poll_seconds']
        lease_seconds = options['lease_seconds']
        if poll_seconds <= 0:
            raise CommandError('--poll-seconds precisa ser maior que zero.')
        if lease_seconds <= 0:
            raise CommandError('--lease-seconds precisa ser maior que zero.')

        worker_id = f'{socket.gethostname()}:{os.getpid()}'
        stopping = threading.Event()

        def request_shutdown(signum, frame):
            if not stopping.is_set():
                self.stdout.write(
                    self.style.WARNING(
                        f'Worker {worker_id} recebeu sinal {signum}; encerrando com segurança.'
                    )
                )
                stopping.set()

        previous_handlers = {}
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, request_shutdown)

        self.stdout.write(f'Worker tático iniciado: {worker_id}')
        try:
            while not stopping.is_set():
                task = None
                try:
                    task = claim_next_task(
                        worker_id=worker_id,
                        lease_seconds=lease_seconds,
                    )
                    if task is not None:
                        execute_claimed_task(task_id=task.pk, worker_id=worker_id)
                except Exception:
                    logger.exception(
                        'Falha inesperada no ciclo do worker tático',
                        extra={'worker_id': worker_id},
                    )
                    if options['once']:
                        raise
                if options['once']:
                    break
                if task is None:
                    stopping.wait(poll_seconds)
        finally:
            for signum, previous_handler in previous_handlers.items():
                signal.signal(signum, previous_handler)
            self.stdout.write(f'Worker tático encerrado: {worker_id}')
