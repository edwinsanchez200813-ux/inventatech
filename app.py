from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'clave_secreta_inventatech'

def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",  # Tu contraseña de MySQL
        database="inventatech_db"
    )
    return connection

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT p.id, p.nombre, p.sku, p.costo, p.precio, p.stock, c.nombre AS categoria, p.categoria_id 
        FROM productos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.id DESC
    """)
    productos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM categorias")
    categorias = cursor.fetchall()

    cursor.execute("""
        SELECT v.id, p.nombre AS producto, p.sku, v.cantidad, v.precio_unitario, v.total, v.fecha 
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        ORDER BY v.fecha DESC
    """)
    ventas = cursor.fetchall()

    total_ingresos = sum(v['total'] for v in ventas)
    
    cursor.close()
    conn.close()
    
    return render_template('index.html', productos=productos, categorias=categorias, ventas=ventas, total_ingresos=total_ingresos)

@app.route('/login', methods=['POST'])
def login():
    data = request.form if request.form else request.get_json()
    usuario = data.get('email') or data.get('username')
    contrasena = data.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE username = %s AND password = %s", (usuario, contrasena))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user:
        session['usuario'] = user['username']
        session['rol'] = user['rol']
        return redirect(url_for('index'))
    else:
        return "Credenciales incorrectas. <a href='/'>Volver</a>", 401

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    nombre = request.form['nombre']
    sku = request.form['sku']
    costo = float(request.form['costo'])
    precio = float(request.form['precio'])
    stock_nuevo = int(request.form['stock'])
    categoria_id = request.form['categoria_id']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verificar si el producto ya existe por su nombre exacto
    cursor.execute("SELECT * FROM productos WHERE nombre = %s", (nombre,))
    producto_existente = cursor.fetchone()
    
    if producto_existente:
        # Si ya existe, SUMAR al stock actual y actualizar precio/costo si es necesario
        nuevo_stock = producto_existente['stock'] + stock_nuevo
        cursor.execute(
            "UPDATE productos SET stock = %s, costo = %s, precio = %s WHERE id = %s",
            (nuevo_stock, costo, precio, producto_existente['id'])
        )
        flash(f"El producto ya existía. Se sumaron {stock_nuevo} unidades al stock (Total: {nuevo_stock}).", "success")
    else:
        # Si no existe, crear registro nuevo
        cursor.execute(
            "INSERT INTO productos (nombre, sku, costo, precio, stock, categoria_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (nombre, sku, costo, precio, stock_nuevo, categoria_id)
        )
        flash(f"¡Producto registrado exitosamente!", "success")
        
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

# RUTA PARA EDITAR PRODUCTO DIRECTAMENTE
@app.route('/editar_producto', methods=['POST'])
def editar_producto():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    producto_id = request.form['producto_id']
    nuevo_precio = request.form['precio']
    nuevo_costo = request.form['costo']
    nuevo_stock = request.form['stock']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE productos SET precio = %s, costo = %s, stock = %s WHERE id = %s", (nuevo_precio, nuevo_costo, nuevo_stock, producto_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Producto actualizado correctamente.", "success")
    return redirect(url_for('index'))

@app.route('/vender_producto', methods=['POST'])
def vender_producto():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    producto_id = request.form['producto_id']
    cantidad = int(request.form['cantidad'])
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
    prod = cursor.fetchone()
    
    if prod:
        if prod['stock'] >= cantidad:
            nuevo_stock = prod['stock'] - cantidad
            total_venta = cantidad * float(prod['precio'])
            
            cursor.execute("UPDATE productos SET stock = %s WHERE id = %s", (nuevo_stock, producto_id))
            cursor.execute(
                "INSERT INTO ventas (producto_id, cantidad, precio_unitario, total) VALUES (%s, %s, %s, %s)",
                (producto_id, cantidad, prod['precio'], total_venta)
            )
            conn.commit()
            flash(f"¡Venta realizada con éxito! Se descontaron {cantidad} unidades de {prod['nombre']}.", "success")
        else:
            flash(f"¡Error! Stock insuficiente. Solo quedan {prod['stock']} unidades disponibles.", "danger")
    
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/eliminar/<int:id>')
def eliminar_producto(id):
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)