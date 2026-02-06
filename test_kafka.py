"""Simple Kafka test script to debug connectivity"""
from kafka import KafkaConsumer, TopicPartition
import os
from dotenv import load_dotenv

load_dotenv()

bootstrap = os.getenv("KAFKA_BOOTSTRAP", "127.0.0.1:29092")
group = os.getenv("KAFKA_GROUP", "test-consumer")

print(f"Bootstrap: {bootstrap}")
print(f"Group: {group}")

# Create consumer
consumer = KafkaConsumer(
    bootstrap_servers=bootstrap,
    auto_offset_reset='earliest',
    group_id=group + "-test",
    consumer_timeout_ms=10000
)

# List topics
print("\n📋 Available topics:")
topics = consumer.topics()
for t in topics:
    print(f"  - {t}")

# Check specific topic
topic = 'banking_server.public.customers'
if topic in topics:
    print(f"\n✅ Topic '{topic}' exists!")
    
    # Get partitions
    partitions = consumer.partitions_for_topic(topic)
    print(f"Partitions: {partitions}")
    
    # Assign and seek to beginning
    tp = TopicPartition(topic, 0)
    consumer.assign([tp])
    consumer.seek_to_beginning(tp)
    
    # Get end offset
    end = consumer.end_offsets([tp])
    begin = consumer.beginning_offsets([tp])
    print(f"Beginning offset: {begin}")
    print(f"End offset: {end}")
    print(f"Total messages: {end[tp] - begin[tp]}")
    
    # Try to read a few messages
    print("\n📨 Trying to read messages...")
    count = 0
    for msg in consumer:
        print(f"  Message: {msg.value[:100]}...")
        count += 1
        if count >= 3:
            break
    
    if count == 0:
        print("  No messages received!")
else:
    print(f"\n❌ Topic '{topic}' not found!")

consumer.close()
