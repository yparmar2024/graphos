FROM bkimminich/juice-shop:v19.0.0
EXPOSE 3000
# The distroless upstream image has no shell or PATH-resolved node binary.
HEALTHCHECK --interval=3s --timeout=5s --start-period=15s --retries=30 CMD ["/nodejs/bin/node", "-e", "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"]
