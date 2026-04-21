"""Trigger executor — fires KNX telegrams and webhook GET requests."""

import asyncio
from typing import Optional

import aiohttp
from loguru import logger

from app.knx_manager import KNXManager


async def execute_triggers(
    zone_config: dict,
    transition: str,
    knx_manager: KNXManager,
    camera_name: str = "",
) -> None:
    """Fire all triggers for a zone on a state transition.

    Args:
        zone_config: The zone dict containing "triggers" list.
        transition: "on" or "off".
        knx_manager: Shared KNX connection manager.
        camera_name: For logging.
    """
    zone_name = zone_config.get("name", zone_config["id"][:8])
    triggers = zone_config.get("triggers", [])

    for trigger in triggers:
        trigger_type = trigger.get("type", "")
        try:
            if trigger_type == "knx":
                await _fire_knx(trigger, transition, knx_manager, camera_name, zone_name)
            elif trigger_type == "webhook":
                await _fire_webhook(trigger, transition, camera_name, zone_name)
        except Exception as e:
            logger.error(f"[{camera_name}] Trigger error ({trigger_type}): {e}")


async def _fire_knx(
    trigger: dict,
    transition: str,
    knx_manager: KNXManager,
    camera_name: str,
    zone_name: str,
) -> None:
    group_address = trigger.get("group_address", "")
    dpt = trigger.get("dpt", "boolean")
    value = trigger.get("on_value", 1) if transition == "on" else trigger.get("off_value", 0)

    if not group_address:
        return

    ok = await knx_manager.send(group_address, dpt, int(value))
    if ok:
        logger.info(f"[{camera_name}] Zone '{zone_name}' {transition.upper()} → KNX {group_address} = {value}")


async def _fire_webhook(
    trigger: dict,
    transition: str,
    camera_name: str,
    zone_name: str,
) -> None:
    # Use dedicated on_url / off_url; fall back to legacy "url" for on
    if transition == "on":
        url = trigger.get("on_url") or trigger.get("url", "")
    else:
        url = trigger.get("off_url", "")

    if not url:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                logger.info(
                    f"[{camera_name}] Zone '{zone_name}' {transition.upper()} → Webhook GET {url} → {resp.status}"
                )
    except asyncio.TimeoutError:
        logger.warning(f"[{camera_name}] Webhook timeout: {url}")
    except Exception as e:
        logger.warning(f"[{camera_name}] Webhook error: {e}")
