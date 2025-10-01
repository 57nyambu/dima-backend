# marketplace/management/commands/update_marketplace_cache.py
from django.core.management.base import BaseCommand
from django.core.cache import cache
from apps.marketplace.services import AggregationService


class Command(BaseCommand):
    help = 'Update marketplace cache data'
    
    def handle(self, *args, **options):
        self.stdout.write('Updating marketplace cache...')
        
        # Clear existing cache
        cache.clear()
        
        # Pre-populate homepage data
        homepage_data = AggregationService.get_homepage_data()
        cache.set('homepage_data:anonymous', homepage_data, 1800)
        
        # Update search indexes
        AggregationService.update_search_indexes()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully updated marketplace cache')
        )


