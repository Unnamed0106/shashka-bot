import asyncio
import json
import os
import uuid
from aiohttp import web
import aiohttp

# O'yinlar saqlanadigan joy
games = {}

# Boshlang'ich taxta
def new_board():
    board = [[None]*8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 1:
                if r < 3:
                    board[r][c] = 'w'
                elif r > 4:
                    board[r][c] = 'r'
    return board

def get_moves(board, r, c, jump_only=False):
    piece = board[r][c]
    if not piece:
        return []
    moves = []
    dirs = []
    if piece == 'r':
        dirs += [(-1, -1), (-1, 1)]
    elif piece == 'w':
        dirs += [(1, -1), (1, 1)]
    elif piece in ('R', 'W'):
        dirs = [(-1,-1),(-1,1),(1,-1),(1,1)]

    for dr, dc in dirs:
        nr, nc = r+dr, c+dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            if board[nr][nc] is None and not jump_only:
                moves.append({'r': nr, 'c': nc, 'jump': False})
            elif board[nr][nc] and board[nr][nc].lower() != piece.lower():
                jr, jc = nr+dr, nc+dc
                if 0 <= jr < 8 and 0 <= jc < 8 and board[jr][jc] is None:
                    moves.append({'r': jr, 'c': jc, 'jump': True, 'cr': nr, 'cc': nc})
    return moves

def has_any_jump(board, color):
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p and p.lower() == color:
                if any(m['jump'] for m in get_moves(board, r, c, True)):
                    return True
    return False

def count_pieces(board):
    r = sum(1 for row in board for p in row if p and p.lower()=='r')
    w = sum(1 for row in board for p in row if p and p.lower()=='w')
    return r, w

async def send_state(game):
    rc, wc = count_pieces(game['board'])
    state = {
        'type': 'state',
        'board': game['board'],
        'turn': game['turn'],
        'red_count': rc,
        'white_count': wc,
        'selected': game.get('selected'),
        'possible': game.get('possible', []),
    }
    for ws in game['players'].values():
        try:
            await ws.send_json(state)
        except:
            pass

async def websocket_handler(request):
    game_id = request.match_info['game_id']
    color = request.match_info['color']

    if game_id not in games:
        return web.Response(status=404)

    game = games[game_id]

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    game['players'][color] = ws
    await ws.send_json({'type': 'connected', 'color': color, 'waiting': len(game['players']) < 2})

    if len(game['players']) == 2:
        await send_state(game)

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            if data['type'] == 'move':
                r, c = data['r'], data['c']
                board = game['board']
                turn = game['turn']

                if color != turn:
                    continue

                if game['selected'] is None:
                    piece = board[r][c]
                    if not piece or piece.lower() != turn:
                        continue
                    force_jump = has_any_jump(board, turn)
                    moves = get_moves(board, r, c, force_jump)
                    if not moves:
                        continue
                    game['selected'] = (r, c)
                    game['possible'] = moves
                else:
                    mv = next((m for m in game['possible'] if m['r']==r and m['c']==c), None)
                    if mv:
                        sr, sc = game['selected']
                        board[r][c] = board[sr][sc]
                        board[sr][sc] = None
                        if mv['jump']:
                            board[mv['cr']][mv['cc']] = None
                        if turn == 'r' and r == 0:
                            board[r][c] = 'R'
                        elif turn == 'w' and r == 7:
                            board[r][c] = 'W'

                        chain = [m for m in get_moves(board, r, c, True) if m['jump']] if mv['jump'] else []
                        if chain:
                            game['selected'] = (r, c)
                            game['possible'] = chain
                        else:
                            game['turn'] = 'w' if turn == 'r' else 'r'
                            game['selected'] = None
                            game['possible'] = []
                    else:
                        piece = board[r][c]
                        if piece and piece.lower() == turn:
                            force_jump = has_any_jump(board, turn)
                            moves = get_moves(board, r, c, force_jump)
                            game['selected'] = (r, c) if moves else None
                            game['possible'] = moves if moves else []
                        else:
                            game['selected'] = None
                            game['possible'] = []

                rc, wc = count_pieces(board)
                if rc == 0:
                    for ws2 in game['players'].values():
                        try:
                            await ws2.send_json({'type': 'gameover', 'winner': 'white'})
                        except:
                            pass
                    del games[game_id]
                    break
                if wc == 0:
                    for ws2 in game['players'].values():
                        try:
                            await ws2.send_json({'type': 'gameover', 'winner': 'red'})
                        except:
                            pass
                    del games[game_id]
                    break

                await send_state(game)

        elif msg.type == aiohttp.WSMsgType.ERROR:
            break

    return ws

async def create_game(request):
    game_id = str(uuid.uuid4())[:8]
    games[game_id] = {
        'board': new_board(),
        'turn': 'r',
        'players': {},
        'selected': None,
        'possible': [],
    }
    base_url = os.environ.get('BASE_URL', 'http://localhost:8080')
    return web.json_response({'game_id': game_id, 'url': f'{base_url}/game/{game_id}'})

async def serve_html(request):
    game_id = request.match_info['game_id']
    color = request.match_info.get('color', '')
    with open('index.html', 'r') as f:
        html = f.read()
    html = html.replace('GAME_ID_PLACEHOLDER', game_id)
    html = html.replace('COLOR_PLACEHOLDER', color)
    return web.Response(text=html, content_type='text/html')

app = web.Application()
app.router.add_get('/create', create_game)
app.router.add_get('/game/{game_id}', serve_html)
app.router.add_get('/ws/{game_id}/{color}', websocket_handler)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    web.run_app(app, port=port)
