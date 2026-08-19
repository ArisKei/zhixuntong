from fastapi import Depends, Request

from app.clients.factory import Clients


def get_clients(request: Request) -> Clients:
    return request.app.state.clients
