from dns_server import DNSServer

if __name__ == "__main__":
    server = DNSServer(
        local_ip="10.29.216.160",
        local_port=53,
        upstream_server=('8.8.8.8', 53),
        db_file="database.txt"
    )
    server.start()