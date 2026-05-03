# This file holds the in-memory database so all modules share the SAME data
devices = {}
ota_log = []
anomaly_count = 0

def increment_anomaly():
    global anomaly_count
    anomaly_count += 1