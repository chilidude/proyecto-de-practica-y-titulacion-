from flask import Flask, render_template, request, redirect, send_file, flash
import sqlite3
import pandas as pd
from io import BytesIO

from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "turismo_andino_secret"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

#  DATABASE 
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

#  USER MODEL 
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user["id"], user["username"], user["password"])
    return None

#  LOGIN 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            user_obj = User(user["id"], user["username"], user["password"])
            login_user(user_obj)
            flash("¡Has iniciado sesión exitosamente!", "success")
            return redirect("/dashboard")
        else:
            flash("Usuario o contraseña incorrectos", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Has cerrado sesión", "info")
    return redirect("/login")

#  INVENTARIO 
@app.route("/")
@app.route("/recursos")
@login_required
def index():
    conn = get_db()
    recursos = conn.execute("SELECT * FROM recursos").fetchall()
    conn.close()
    return render_template("index.html", recursos=recursos)

@app.route("/agregar", methods=["POST"])
@login_required
def agregar():
    nombre = request.form["nombre"]
    cantidad = int(request.form["cantidad"])
    conn = get_db()
    conn.execute("INSERT INTO recursos (nombre,cantidad) VALUES (?,?)", (nombre, cantidad))
    conn.commit()
    conn.close()
    flash(f"Recurso '{nombre}' agregado correctamente", "success")
    return redirect("/")

@app.route("/eliminar/<int:id>")
@login_required
def eliminar(id):
    conn = get_db()
    recurso = conn.execute("SELECT nombre FROM recursos WHERE id=?", (id,)).fetchone()
    if recurso:
        conn.execute("DELETE FROM recursos WHERE id=?", (id,))
        conn.commit()
        flash(f"Recurso '{recurso['nombre']}' eliminado", "warning")
    else:
        flash("El recurso no existe", "danger")
    conn.close()
    return redirect("/")

#  EDITAR RECURSO 
@app.route("/editar/<int:id>")
@login_required
def editar(id):
    conn = get_db()
    recurso = conn.execute("SELECT * FROM recursos WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template("editar.html", recurso=recurso)

@app.route("/editar/<int:id>/guardar", methods=["POST"])
@login_required
def guardar_edicion(id):
    nombre = request.form["nombre"]
    cantidad = int(request.form["cantidad"])
    conn = get_db()
    conn.execute("UPDATE recursos SET nombre=?, cantidad=? WHERE id=?", (nombre, cantidad, id))
    conn.commit()
    conn.close()
    flash(f"Recurso '{nombre}' actualizado correctamente", "success")
    return redirect("/")

#  REGISTRAR MERMA 
@app.route("/merma/<int:id>")
@login_required
def merma(id):
    conn = get_db()
    recurso = conn.execute("SELECT * FROM recursos WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template("merma.html", recurso=recurso)

@app.route("/merma/<int:id>/guardar", methods=["POST"])
@login_required
def guardar_merma(id):
    cantidad = int(request.form["cantidad"])
    fecha = request.form["fecha"]
    conn = get_db()
    conn.execute("INSERT INTO merma (recurso_id, cantidad, fecha) VALUES (?, ?, ?)", (id, cantidad, fecha))
    conn.execute("UPDATE recursos SET cantidad = cantidad - ? WHERE id=?", (cantidad, id))
    conn.commit()
    conn.close()
    flash(f"Merma de {cantidad} registrada correctamente", "success")
    return redirect("/")

@app.route("/merma/eliminar/<int:id>")
@login_required
def eliminar_merma(id):
    conn = get_db()
    merma = conn.execute("SELECT m.id, r.nombre, m.cantidad FROM merma m JOIN recursos r ON r.id = m.recurso_id WHERE m.id=?", (id,)).fetchone()
    if merma:
        conn.execute("DELETE FROM merma WHERE id=?", (id,))
        conn.commit()
        flash(f"Merma de {merma['cantidad']} del recurso '{merma['nombre']}' eliminada", "warning")
    else:
        flash("Merma no encontrada", "danger")
    conn.close()
    return redirect("/dashboard")

#  TRABAJADORES 
@app.route("/trabajadores")
@login_required
def trabajadores():
    conn = get_db()
    trabajadores = conn.execute("SELECT * FROM trabajadores").fetchall()
    conn.close()
    return render_template("trabajadores.html", trabajadores=trabajadores)

@app.route("/trabajadores/agregar", methods=["POST"])
@login_required
def agregar_trabajador():
    nombre = request.form["nombre"]
    cargo = request.form["cargo"]
    conn = get_db()
    conn.execute("INSERT INTO trabajadores (nombre,cargo) VALUES (?,?)", (nombre, cargo))
    conn.commit()
    conn.close()
    flash(f"Trabajador '{nombre}' agregado correctamente", "success")
    return redirect("/trabajadores")

@app.route("/trabajadores/eliminar/<int:id>")
@login_required
def eliminar_trabajador(id):
    conn = get_db()
    trabajador = conn.execute("SELECT nombre FROM trabajadores WHERE id=?", (id,)).fetchone()
    if trabajador:
        conn.execute("DELETE FROM trabajadores WHERE id=?", (id,))
        conn.commit()
        flash(f"Trabajador '{trabajador['nombre']}' eliminado", "warning")
    else:
        flash("Trabajador no encontrado", "danger")
    conn.close()
    return redirect("/trabajadores")

#  ASIGNACIONES 
@app.route("/asignaciones")
@login_required
def asignaciones():
    trabajador_id = request.args.get("trabajador_id")
    recurso_id = request.args.get("recurso_id")

    conn = get_db()
    trabajadores = conn.execute("SELECT * FROM trabajadores").fetchall()
    recursos = conn.execute("SELECT * FROM recursos WHERE cantidad > 0").fetchall()

    query = "SELECT a.id, a.trabajador, a.recurso, a.cantidad, a.fecha FROM asignaciones a WHERE 1=1"
    params = []

    if trabajador_id:
        trabajador = conn.execute("SELECT nombre FROM trabajadores WHERE id=?", (trabajador_id,)).fetchone()
        if trabajador:
            query += " AND a.trabajador = ?"
            params.append(trabajador["nombre"])

    if recurso_id:
        recurso = conn.execute("SELECT nombre FROM recursos WHERE id=?", (recurso_id,)).fetchone()
        if recurso:
            query += " AND a.recurso = ?"
            params.append(recurso["nombre"])

    asignaciones = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("asignaciones.html", asignaciones=asignaciones, recursos=recursos, trabajadores=trabajadores)

@app.route("/asignaciones/agregar", methods=["POST"])
@login_required
def agregar_asignacion():
    trabajador_id = request.form["trabajador_id"]
    recurso_id = request.form["recurso_id"]
    cantidad = int(request.form["cantidad"])
    fecha = request.form["fecha"]

    conn = get_db()
    trabajador = conn.execute("SELECT nombre FROM trabajadores WHERE id=?", (trabajador_id,)).fetchone()
    recurso = conn.execute("SELECT nombre, cantidad FROM recursos WHERE id=?", (recurso_id,)).fetchone()

    if not trabajador or not recurso:
        flash("Trabajador o recurso no válido", "danger")
        conn.close()
        return redirect("/asignaciones")

    if cantidad > recurso["cantidad"]:
        flash(f"No hay suficiente inventario para '{recurso['nombre']}'. Disponible: {recurso['cantidad']}", "danger")
        conn.close()
        return redirect("/asignaciones")

    conn.execute(
        "INSERT INTO asignaciones (trabajador, recurso, cantidad, fecha) VALUES (?, ?, ?, ?)",
        (trabajador["nombre"], recurso["nombre"], cantidad, fecha)
    )
    conn.execute(
        "UPDATE recursos SET cantidad = cantidad - ? WHERE id=?",
        (cantidad, recurso_id)
    )
    conn.commit()
    conn.close()
    flash(f"Asignación de {cantidad} '{recurso['nombre']}' a {trabajador['nombre']} registrada correctamente", "success")
    return redirect("/asignaciones")

@app.route("/asignaciones/eliminar/<int:id>")
@login_required
def eliminar_asignacion(id):
    conn = get_db()
    asignacion = conn.execute("SELECT * FROM asignaciones WHERE id=?", (id,)).fetchone()
    if asignacion:
        recurso = conn.execute("SELECT cantidad FROM recursos WHERE nombre=?", (asignacion["recurso"],)).fetchone()
        if recurso:
            conn.execute("UPDATE recursos SET cantidad = cantidad + ? WHERE nombre=?", (asignacion["cantidad"], asignacion["recurso"]))
        conn.execute("DELETE FROM asignaciones WHERE id=?", (id,))
        conn.commit()
        flash(f"Asignación de {asignacion['cantidad']} '{asignacion['recurso']}' eliminada", "warning")
    else:
        flash("Asignación no encontrada", "danger")
    conn.close()
    return redirect("/asignaciones")

#  DASHBOARD 
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    total_items = conn.execute("SELECT COUNT(*) FROM recursos").fetchone()[0]
    total_recursos = conn.execute("SELECT SUM(cantidad) FROM recursos").fetchone()[0] or 0
    total_merma = conn.execute("SELECT SUM(cantidad) FROM merma").fetchone()[0] or 0

    recursos_data = conn.execute("SELECT nombre, cantidad FROM recursos").fetchall()
    recursos_nombres = [r["nombre"] for r in recursos_data]
    recursos_cantidades = [r["cantidad"] for r in recursos_data]

    merma_data = conn.execute("""
        SELECT r.nombre, SUM(m.cantidad) as total
        FROM merma m
        JOIN recursos r ON r.id = m.recurso_id
        GROUP BY r.nombre
    """).fetchall()
    merma_nombres = [m["nombre"] for m in merma_data]
    merma_cantidades = [m["total"] for m in merma_data]

    conn.close()
    return render_template(
        "dashboard.html",
        total_items=total_items,
        total_recursos=total_recursos,
        total_merma=total_merma,
        recursos_nombres=recursos_nombres,
        recursos_cantidades=recursos_cantidades,
        merma_nombres=merma_nombres,
        merma_cantidades=merma_cantidades
    )
#  REPORTES 
@app.route("/reportes")
@login_required
def reportes():
    conn = get_db()
    
    # Inventario
    inventario = conn.execute("SELECT * FROM recursos").fetchall()
    
    # Mermas
    mermas = conn.execute("""
        SELECT m.id, r.nombre, m.cantidad, m.fecha
        FROM merma m
        JOIN recursos r ON r.id = m.recurso_id
    """).fetchall()
    
    # Asignaciones
    asignaciones = conn.execute("""
        SELECT a.id, a.trabajador, a.recurso, a.cantidad, a.fecha
        FROM asignaciones a
    """).fetchall()
    
    conn.close()
    
    return render_template(
        "reportes.html",
        inventario=inventario,
        mermas=mermas,
        asignaciones=asignaciones
    )
#  EXPORTAR EXCEL 
@app.route("/exportar_trabajadores")
@login_required
def exportar_trabajadores():
    conn = get_db()
    trabajadores = conn.execute("SELECT * FROM trabajadores").fetchall()
    conn.close()

    df = pd.DataFrame([dict(row) for row in trabajadores])
    df = df[["id", "nombre", "cargo"]].sort_values(by="nombre")

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Trabajadores")
    output.seek(0)
    return send_file(output, download_name="trabajadores.xlsx", as_attachment=True)

@app.route("/exportar_inventario")
@login_required
def exportar_inventario():
    conn = get_db()
    recursos = conn.execute("SELECT * FROM recursos").fetchall()
    conn.close()

    df = pd.DataFrame([dict(row) for row in recursos])
    df = df[["id", "nombre", "cantidad"]].sort_values(by="nombre")

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Inventario")
    output.seek(0)
    return send_file(output, download_name="inventario.xlsx", as_attachment=True)

@app.route("/exportar_merma")
@login_required
def exportar_merma():
    conn = get_db()
    mermas = conn.execute("""
        SELECT m.id, r.nombre as recurso, m.cantidad, m.fecha
        FROM merma m
        JOIN recursos r ON r.id = m.recurso_id
    """).fetchall()
    conn.close()

    df = pd.DataFrame([dict(row) for row in mermas])
    df = df[["id", "recurso", "cantidad", "fecha"]].sort_values(by=["fecha", "recurso"])

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Merma")
    output.seek(0)
    return send_file(output, download_name="merma.xlsx", as_attachment=True)

@app.route("/exportar_asignaciones")
@login_required
def exportar_asignaciones():
    conn = get_db()
    asignaciones = conn.execute("SELECT * FROM asignaciones").fetchall()
    conn.close()

    df = pd.DataFrame([dict(row) for row in asignaciones])
    df = df[["id", "trabajador", "recurso", "cantidad", "fecha"]].sort_values(by=["fecha", "trabajador"])

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Asignaciones")
    output.seek(0)
    return send_file(output, download_name="asignaciones.xlsx", as_attachment=True)
#  EXPORTAR INVENTARIO A EXCEL 
@app.route("/exportar_excel")
@login_required
def exportar_excel():
    conn = get_db()
    inventario = conn.execute("SELECT * FROM recursos").fetchall()
    conn.close()

    import pandas as pd
    from io import BytesIO

    # Convertimos a DataFrame y ordenamos por nombre
    df = pd.DataFrame([dict(row) for row in inventario])
    df = df[["id", "nombre", "cantidad"]].sort_values(by="nombre")

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Inventario")
    output.seek(0)
    return send_file(output, download_name="inventario.xlsx", as_attachment=True)

#  CREAR BASE DE DATOS 
if __name__ == "__main__":
    conn = sqlite3.connect("database.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recursos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            cantidad INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS merma(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recurso_id INTEGER,
            cantidad INTEGER,
            fecha TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trabajadores(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            cargo TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS asignaciones(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trabajador TEXT,
            recurso TEXT,
            cantidad INTEGER,
            fecha TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)
    password = generate_password_hash("admin")
    conn.execute("INSERT OR IGNORE INTO usuarios(username,password) VALUES('admin',?)", (password,))
    conn.commit()
    conn.close()

    app.run(debug=True)