"""Assina o tópico MQTT publicado pelo firmware ESP32 (src/iot/firmware/aquaguard_esp32)
e alimenta o TelemetryStore, disparando a mesma análise proativa do endpoint HTTP.
Mesmo broker HiveMQ Cloud do projeto CardioIA — credenciais em MQTT_* no .env."""
import json
import logging

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from pydantic import ValidationError

from ..config import settings
from ..schemas import TelemetryIn
from . import agent
from .telemetry import store
from .weather import get_weather

logger = logging.getLogger("aquaguard.mqtt")


def _ao_conectar(client: mqtt.Client, _userdata: object, _connect_flags: object, codigo_motivo: object,
                  _properties: object) -> None:
    if codigo_motivo == 0:
        client.subscribe(settings.mqtt_topic)
        logger.info("Conectado ao broker MQTT, assinando %s", settings.mqtt_topic)
    else:
        logger.warning("Falha ao conectar no broker MQTT: %s", codigo_motivo)


def _ao_receber_mensagem(_client: mqtt.Client, _userdata: object, msg: mqtt.MQTTMessage) -> None:
    try:
        dados = json.loads(msg.payload)
        leitura = TelemetryIn(**dados)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, ValidationError) as e:
        logger.warning("Mensagem MQTT em formato inesperado: %s", e)
        return

    if leitura.source != "real" and leitura.scenario:
        store.scenario = leitura.scenario.value
    rec = store.add(leitura)
    tel, weather = store.latest(), get_weather(store.scenario)
    agent.proactive_analysis(tel, weather)
    logger.info("Leitura MQTT armazenada (%s): rio=%.1fcm chuva=%.1f%%",
                rec["device_ref"], leitura.river_level_cm, leitura.rain_intensity)


def iniciar_mqtt_listener() -> None:
    """Conecta ao broker MQTT em segundo plano, sem derrubar o backend se a conexão falhar."""
    if not settings.mqtt_server:
        logger.info("MQTT_SERVER não configurado — listener de IoT desligado (use o simulador HTTP).")
        return

    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    client.username_pw_set(settings.mqtt_user, settings.mqtt_password)
    client.tls_set()
    client.on_connect = _ao_conectar
    client.on_message = _ao_receber_mensagem

    try:
        client.connect(settings.mqtt_server, settings.mqtt_port, keepalive=60)
        client.loop_start()
    except Exception as e:
        logger.warning("Não foi possível conectar ao broker MQTT agora: %s", e)
