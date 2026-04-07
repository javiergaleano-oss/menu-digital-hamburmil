from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "BASE DE DATOS MENU COMIDAS RAPIDAS.csv")


# ==============================
# NUMERO DE PEDIDO (REINICIO DIARIO)
# ==============================
def generar_numero_pedido():
    archivo = os.path.join(BASE_DIR, "contador_pedidos.json")
    hoy = datetime.now().strftime("%Y-%m-%d")

    if not os.path.exists(archivo):
        data = {"fecha": hoy, "contador": 1}
    else:
        with open(archivo, "r") as f:
            data = json.load(f)

        if data["fecha"] != hoy:
            data["contador"] = 1
            data["fecha"] = hoy
        else:
            data["contador"] += 1

    with open(archivo, "w") as f:
        json.dump(data, f)

    return data["contador"]


# ==============================
# MENU
# ==============================
def cargar_menu():
    df = pd.read_csv(CSV_PATH, encoding="utf-8", sep=";")
    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "", regex=False)
    df["REFERENCIA"] = df["REFERENCIA"].astype(str)
    df["PRECIO"] = pd.to_numeric(df["PRECIO"], errors="coerce").fillna(0)
    return df


@app.context_processor
def carrito_global():
    carrito = session.get("carrito", [])
    total = sum(item["PRECIO"] for item in carrito)
    return dict(carrito_cantidad=len(carrito), carrito_total=total)


# ==============================
# RUTAS
# ==============================
@app.route("/")
def index():
    menu = cargar_menu()
    categorias = sorted(menu["CATEGORIA"].dropna().unique())
    return render_template("categorias.html", categorias=categorias)


@app.route("/categoria/<nombre>")
def ver_categoria(nombre):
    menu = cargar_menu()
    productos = menu[menu["CATEGORIA"] == nombre]
    return render_template("productos.html", categoria=nombre, productos=productos.to_dict(orient="records"))


# ==============================
# AGREGAR PRODUCTOS CON CANTIDAD
# ==============================
@app.route("/agregar", methods=["POST"])
def agregar():
    if "carrito" not in session:
        session["carrito"] = []

    carrito = session["carrito"]
    cantidad = int(request.form.get("cantidad") or 1)

    for _ in range(cantidad):
        carrito.append({
            "REFERENCIA": request.form.get("referencia"),
            "DESCRIPCION": request.form.get("descripcion"),
            "PRECIO": float(request.form.get("precio")),
            "CATEGORIA": request.form.get("categoria"),
            "SALSAS": ", ".join(request.form.getlist("salsas")),
            "EXTRAS": ", ".join(request.form.getlist("extras"))
        })

    session["carrito"] = carrito
    return redirect(url_for("ver_carrito"))


# ==============================
# ELIMINAR
# ==============================
@app.route("/eliminar/<int:index>")
def eliminar(index):
    carrito = session.get("carrito", [])
    if 0 <= index < len(carrito):
        carrito.pop(index)
    session["carrito"] = carrito
    return redirect(url_for("ver_carrito"))


# ==============================
# DUPLICAR
# ==============================
@app.route("/duplicar/<int:index>")
def duplicar(index):
    carrito = session.get("carrito", [])
    if 0 <= index < len(carrito):
        carrito.append(carrito[index].copy())
    session["carrito"] = carrito
    return redirect(url_for("ver_carrito"))


# ==============================
# EDITAR
# ==============================
@app.route("/editar/<int:index>")
def editar(index):
    carrito = session.get("carrito", [])

    if not carrito or index >= len(carrito):
        flash("⚠️ Producto no disponible")
        return redirect(url_for("ver_carrito"))

    return render_template("editar_producto.html", item=carrito[index], index=index)


@app.route("/actualizar/<int:index>", methods=["POST"])
def actualizar(index):
    carrito = session.get("carrito", [])

    if not carrito or index >= len(carrito):
        return redirect(url_for("ver_carrito"))

    carrito[index]["SALSAS"] = ", ".join(request.form.getlist("salsas"))
    carrito[index]["EXTRAS"] = ", ".join(request.form.getlist("extras"))

    session["carrito"] = carrito
    return redirect(url_for("ver_carrito"))


# ==============================
# CARRITO
# ==============================
@app.route("/carrito")
def ver_carrito():
    carrito = session.get("carrito", [])
    total = sum(item["PRECIO"] for item in carrito)
    return render_template("carrito.html", carrito=carrito, total=total)


# ==============================
# FINALIZAR
# ==============================
@app.route("/finalizar", methods=["POST"])
def finalizar():

    carrito = session.get("carrito", [])
    total = sum(item["PRECIO"] for item in carrito)

    pago_efectivo = float(request.form.get("pago_efectivo") or 0)
    pago_nequi = float(request.form.get("pago_nequi") or 0)

    total_pagado = pago_efectivo + pago_nequi

    restante = 0
    cambio = 0

    if total_pagado < total:
        restante = total - total_pagado
    else:
        cambio = total_pagado - total

    pedido = {
        "numero": generar_numero_pedido(),
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nombre": request.form.get("nombre"),
        "tipo_entrega": request.form.get("tipo_entrega"),
        "direccion": request.form.get("direccion"),
        "mesa": request.form.get("mesa"),
        "efectivo": pago_efectivo,
        "nequi": pago_nequi,
        "restante": restante,
        "cambio": cambio
    }

    session["pedido"] = pedido

    return render_template("confirmacion.html", pedido=pedido, carrito=carrito, total=total)


# ==============================
# TICKET
# ==============================
@app.route("/ticket")
def ticket():
    carrito = session.get("carrito", [])
    pedido = session.get("pedido", {})
    total = sum(item["PRECIO"] for item in carrito)
    return render_template("ticket.html", carrito=carrito, total=total, pedido=pedido)


@app.route("/limpiar")
def limpiar():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)