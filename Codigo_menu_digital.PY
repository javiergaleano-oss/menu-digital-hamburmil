from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Necesario para usar session

# ==============================
# CONFIGURACIÓN
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "BASE DE DATOS MENU COMIDAS RAPIDAS.csv")


# ==============================
# CARGAR MENU
# ==============================
def cargar_menu():
    df = pd.read_csv(CSV_PATH, encoding="utf-8", sep=";")

    df.columns = (
        df.columns
        .str.strip()
        .str.upper()
        .str.replace(" ", "", regex=False)
    )

    df["REFERENCIA"] = df["REFERENCIA"].astype(str)
    df["PRECIO"] = pd.to_numeric(df["PRECIO"], errors="coerce").fillna(0)

    return df


# ==============================
# PAGINA PRINCIPAL (CATEGORIAS)
# ==============================
@app.route("/")
def index():
    menu = cargar_menu()

    categorias = sorted(menu["CATEGORIA"].dropna().unique())

    return render_template("categorias.html", categorias=categorias)


# ==============================
# VER PRODUCTOS POR CATEGORIA
# ==============================
@app.route("/categoria/<nombre>")
def ver_categoria(nombre):
    menu = cargar_menu()
    productos = menu[menu["CATEGORIA"] == nombre]

    return render_template(
        "productos.html",
        categoria=nombre,
        productos=productos.to_dict(orient="records")
    )


# ==============================
# AGREGAR AL CARRITO
# ==============================
@app.route("/agregar", methods=["POST"])
def agregar():

    referencia = request.form.get("referencia")
    descripcion = request.form.get("descripcion")
    precio = float(request.form.get("precio"))

    if "carrito" not in session:
        session["carrito"] = []

    carrito = session["carrito"]

    carrito.append({
        "REFERENCIA": referencia,
        "DESCRIPCION": descripcion,
        "PRECIO": precio
    })

    session["carrito"] = carrito

    return redirect(url_for("ver_carrito"))


# ==============================
# VER CARRITO
# ==============================
@app.route("/carrito")
def ver_carrito():

    carrito = session.get("carrito", [])
    total = sum(item["PRECIO"] for item in carrito)

    return render_template(
        "carrito.html",
        carrito=carrito,
        total=total
    )


# ==============================
# LIMPIAR CARRITO
# ==============================
@app.route("/limpiar")
def limpiar():
    session.pop("carrito", None)
    return redirect(url_for("index"))


# ==============================
# EJECUCION
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)