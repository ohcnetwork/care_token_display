"""
Signal handlers for token display cache invalidation.

This module provides signal handlers that automatically invalidate
the token display cache when relevant data changes (Token status updates,
TokenQueue changes, etc.).
"""

from django.core.cache import cache
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from care.emr.models import SchedulableResource, Token, TokenQueue, TokenSubQueue
from token_display.utils import get_token_display_cache_key


def invalidate_sub_queue_cache(sub_queues: list[TokenSubQueue]):
    """
    Invalidate cache for a list of sub queues.
    """
    for sub_queue in sub_queues:
        cache_key = get_token_display_cache_key(sub_queue.external_id)
        cache.delete(cache_key)


def invalidate_resource_sub_queue_cache(resource: SchedulableResource):
    """
    Invalidate cache for all sub queues in a resource.
    """
    sub_queues = TokenSubQueue.objects.filter(resource=resource)
    invalidate_sub_queue_cache(sub_queues)


@receiver(post_save, sender=Token)
def invalidate_token_display_cache_on_token_post_save(
    sender, instance, created, **kwargs
):
    if instance.sub_queue:
        invalidate_sub_queue_cache([instance.sub_queue])


@receiver(pre_save, sender=Token)
def invalidate_token_display_cache_on_token_pre_save(sender, instance, **kwargs):
    if instance.sub_queue:
        invalidate_sub_queue_cache([instance.sub_queue])


@receiver(post_save, sender=TokenQueue)
def invalidate_token_display_cache_on_queue_save(sender, instance, created, **kwargs):
    invalidate_resource_sub_queue_cache(instance.resource)
