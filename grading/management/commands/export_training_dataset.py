from pathlib import Path
import os
import tempfile
from django.core.management.base import BaseCommand
from grading.models import TrainingCorrection
from grading.training_data import write_dataset


class Command(BaseCommand):
    help = 'Export human-reviewed question and bubble crops; does not train a model.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        target = Path(options['output']).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='training-', suffix='.zip', dir=target.parent)
        try:
            with os.fdopen(fd, 'w+b') as file:
                count = write_dataset(file, TrainingCorrection.objects.all())
            os.replace(temp, target)
        except Exception:
            Path(temp).unlink(missing_ok=True)
            raise
        self.stdout.write(f'Exported {count} approved question samples to {target}')
