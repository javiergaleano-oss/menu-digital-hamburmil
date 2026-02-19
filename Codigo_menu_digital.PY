from flask import Flask, render_template, request
import pandas as pd

app = Flask(__name__)

# ==========================================
# CARGAR BASE DE DATOS
# ==========================================
def cargar_menu():
    df = pd.read_csv(
        "BASE DE DATOS MENU COMIDAS RAPIDAS.csv",
        encoding="utf-8",
        sep=";"   # 👈 ESTA ES LA CLAVE
    )

    df.columns = (
        df.columns
        .str.strip()
        .str.upper()
        .str.replace(" ", "", regex=False)
    )

    print("Columnas detectadas:", df.columns)

    if "REFERENCIA" in df.columns:
        df["REFERENCIA"] = df["REFERENCIA"].astype(str)

    if "PRECIO" in df.columns:
        df["PRECIO"] = pd.to_numeric(df["PRECIO"], errors="coerce")

    return df

# ==========================================
# PAGINA PRINCIPAL
# ==========================================
@app.route("/")
def index():
    menu = cargar_menu()
    return render_template(
        "index.html",
        menu=menu.to_dict(orient="records")
    )


# ==========================================
# PROCESAR PEDIDO
# ==========================================
@app.route("/pedido", methods=["POST"])
def pedido():

    menu = cargar_menu()
    productos_pedido = []
    total = 0

    for _, producto in menu.iterrows():
        referencia = str(producto["REFERENCIA"])
        cantidad = request.form.get(f"cantidad_{referencia}")

        if cantidad and int(cantidad) > 0:
            cantidad = int(cantidad)
            subtotal = cantidad * producto["PRECIO"]

            productos_pedido.append({
                "DESCRIPCION": producto["DESCRIPCION"],
                "PRECIO": producto["PRECIO"],
                "CANTIDAD": cantidad,
                "SUBTOTAL": subtotal
            })

            total += subtotal

    return render_template(
        "pedido.html",
        productos=productos_pedido,
        total=total
    )


if __name__ == "__main__":
    app.run(debug=True)
