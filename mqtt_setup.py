# mqtt_utils.py
import paho.mqtt.client as mqtt

MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPIC = 'iot/detection'

# Set up MQTT client
mqtt_client = mqtt.Client(client_id="Publisher")
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
mqtt_client.loop_start()

def publish_log(message):
    """Publish a log message to the MQTT broker."""
    mqtt_client.publish(MQTT_TOPIC, message)
