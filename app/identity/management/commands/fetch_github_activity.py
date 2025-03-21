import requests
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from identity.models import Author, GitHubActivity

class Command(BaseCommand):
    help = 'Fetch latest public GitHub activity for authors'

    def handle(self, *args, **options):
        authors = Author.objects.exclude(github_username__isnull=True).exclude(github_username__exact='')
        for author in authors:
            url = f'https://api.github.com/users/{author.github_username}/events/public'
            response = requests.get(url)
            if response.status_code != 200:
                self.stderr.write(f"Error fetching events for {author.github_username}: {response.status_code}")
                continue

            events = response.json()
            for event in events:
                event_id = event.get('id')
                # Skip if already processed
                if GitHubActivity.objects.filter(event_id=event_id).exists():
                    continue

                created_at = parse_datetime(event.get('created_at'))
                GitHubActivity.objects.create(
                    author=author,
                    event_id=event_id,
                    event_type=event.get('type'),
                    payload=event,
                    created_at=created_at,
                )
                self.stdout.write(f"Created GitHub activity for {author.github_username} event {event_id}")