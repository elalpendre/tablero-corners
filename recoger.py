# -*- coding: utf-8 -*-
"""
RECOGER LOS DATOS Y DEJARLOS EN datos.json.

Lo ejecuta GitHub cada diez minutos (ver .github/workflows/datos.yml).
Por eso la pagina esta viva aunque el ordenador de casa este apagado:
quien llama al worker es una maquina de GitHub, que no tiene la operadora
espanola delante bloqueandole la IP.

Dos variables de entorno:

    TL_BASE   donde esta el worker. En GitHub, su direccion entera.
              En casa, http://localhost:8787 (el puente ya pone la clave).
    TL_KEY    la clave. Solo hace falta cuando se llama al worker directo.
              NO se escribe nunca aqui: en GitHub vive en los secretos del
              repositorio, y en casa en clave.local, que no sube.

Antes de escribir nada comprueba que en los datos no viaja ninguna clave.
Publicar es irreversible: lo que sale, sale.
"""
from __future__ import print_function

import datetime
import io
import json
import os
import sys

try:
    from urllib.request import urlopen, Request
    from urllib.parse import quote
except ImportError:
    from urllib2 import urlopen, Request
    from urllib import quote

BASE = os.environ.get('TL_BASE', 'http://localhost:8787').rstrip('/')
KEY = os.environ.get('TL_KEY', '')
AQUI = os.path.dirname(os.path.abspath(__file__))


def pide(ruta, espera=150):
    sep = '&' if '?' in ruta else '?'
    url = BASE + ruta + ((sep + 'key=' + quote(KEY)) if KEY else '')
    # Con el agente de Python por delante, Cloudflare contesta 403.
    pet = Request(url, headers={'User-Agent': 'tablero-corners/1.0'})
    try:
        r = urlopen(pet, timeout=espera)
        return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        # Sin la clave dentro del mensaje: el log de GitHub es publico.
        print('  no pude pedir %s: %s' % (ruta, str(e)[:120]))
        return None


def main():
    print('1. pidiendo una pasada')
    r = pide('/refrescar')
    if r is None:
        print('   el worker no contesta. No toco datos.json.')
        return 1
    if r.get('hecho'):
        print('   analizado en %.1f s (%s de %s hoy)'
              % (r.get('ms', 0) / 1000.0, r.get('hoy'), r.get('tope')))
    else:
        print('   no tocaba: %s (%s de %s hoy)'
              % (r.get('motivo'), r.get('hoy'), r.get('tope')))

    print('2. recogiendo')
    live = pide('/api/live') or {}
    ms = live.get('matches', [])
    if not isinstance(ms, list):
        print('   lo que vino no tiene forma de partidos. No toco nada.')
        return 1

    pas = pide('/pasadas') or []
    cup = pide('/cupo') or {}
    tab = pide('/tablas') or {}
    # Las velas salen de casa_log, que es la libreta de la casa: la linea
    # que publico en cada foto. No es lo que apunta el navegador mientras
    # esta abierto; es el mercado, guardado en el servidor.
    vel = pide('/velas') or []
    cor = pide('/corners') or {}
    # La lista corta y los numeros exactos. Las dos SOLO LEEN lo que el
    # worker ya tiene guardado: no gastan ni una llamada a la API, asi
    # que pueden venir en cada recogida sin tocar el cupo.
    lis = pide('/lista-corta?n=10') or {}
    exa = pide('/exactos') or {}
    his = pide('/historico?n=40') or {}

    datos = {
        'momento': datetime.datetime.now(datetime.timezone.utc)
                   .isoformat(timespec='seconds'),
        'updated': live.get('updated'),
        'matches': ms,
        'upcoming': live.get('upcoming', []),
        'pasadas': [{k: p.get(k) for k in ('ts', 'ms', 'cupo', 'vivos', 'error')}
                    for p in (pas if isinstance(pas, list) else [])[:12]],
        'cupo': cup,
        'tablas': tab,
        'velas': vel if isinstance(vel, list) else [],
        'corners': cor if isinstance(cor, dict) else {},
        'corta': lis if isinstance(lis, dict) else {},
        'exactos': exa if isinstance(exa, dict) else {},
        'historico': his if isinstance(his, dict) else {},
    }
    an = sum(1 for m in ms if m.get('analyzed'))
    print('   %d partidos, %d analizados, %d con cuota'
          % (len(ms), an, sum(1 for m in ms if m.get('hasOdds'))))

    crudo = json.dumps(datos, ensure_ascii=False)

    # Nada de claves en lo que se publica. Comprobado, no supuesto.
    malos = ['STATS_KEY', 'api-key', 'apisports', 'Bearer ', 'x-rapidapi']
    if KEY:
        malos.append(KEY)
    for malo in malos:
        if malo and malo in crudo:
            print('ABORTA: en los datos aparece algo que no debe salir.')
            return 1
    print('   sin claves dentro')

    io.open(os.path.join(AQUI, 'datos.json'), 'w',
            encoding='utf-8', newline='\n').write(crudo)
    print('3. escrito datos.json (%d KB)' % (len(crudo) // 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
