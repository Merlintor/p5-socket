from server import WebSocketServer


server = WebSocketServer()
server.run("localhost", 8080)
