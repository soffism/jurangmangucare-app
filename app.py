# app.py (versi filter entitas berdasarkan JenisAnggota)
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import sqlite3
from datetime import datetime
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = "jurangmangucare_secret"

# ------------------------
# DATABASE CONNECTION
# ------------------------
def get_connection(entitas=None):
    if not entitas:
        entitas = 'jurangmangucare'

    if entitas == 'jurangmangucare':
        db_name = 'jurangmangucare.db'
    elif entitas == 'dkm':
        db_name = 'DKMAshShiddiq.db'
    else:
        raise ValueError("Entitas tidak dikenal: {}".format(entitas))

    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

# ------------------------
# ROUTE: Login
# ------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "13579":
            session["user"] = "admin"
            session["entitas"] = "jurangmangucare"  # default admin ke jurangmangucare
            return redirect(url_for("index"))

        elif password == "2468":
            session["user"] = username

            # Cek entitas berdasarkan JenisAnggota
            conn = get_connection('jurangmangucare')
            jmcare_check = conn.execute("""
                SELECT 1 FROM Anggota 
                WHERE KodeAnggota = ? AND JenisAnggota LIKE '%JMCare%'
            """, (username,)).fetchone()
            conn.close()

            if jmcare_check:
                session["entitas"] = "jurangmangucare"
            else:
                session["entitas"] = "dkm"

            return redirect(url_for("index"))

        else:
            return render_template("login.html", error="Username atau password salah.")
    
    return render_template("login.html")
# ------------------------
# ROUTE: Logout
# ------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------------------
# ROUTE: Halaman Utama
# ------------------------
@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    if session["user"] == "admin":
        return redirect(url_for("rekapakhir"))
 
    # Anggota biasa
    entitas = session.get("entitas", "jurangmangucare")
    if entitas == "dkm":
        return redirect(url_for("transaksi_user"))   # DKM Pastikan ini ada 
    else:
        return redirect(url_for("transaksi_jmcare"))  # JurangmanguCare

# ------------------------
# ROUTE: Rekap Akhir (Dinamis Berdasar Entitas)
# ------------------------
@app.route("/rekapakhir", methods=["GET", "POST"])
def rekapakhir():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    # Pilihan entitas disimpan ke session
    if request.method == "POST" and "entitas" in request.form:
        session["entitas"] = request.form["entitas"]

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    # Pilih view dan file template berdasarkan entitas
    if entitas == "dkm":
        rows = conn.execute("SELECT * FROM ViewLaporanRingkasan").fetchall()
    else:
        rows = conn.execute("SELECT * FROM RekapAkhir").fetchall()

    conn.close()
    return render_template("rekap_akhir.html", data=rows)


@app.route("/rekapakhir/export")
def export_rekapakhir():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    if entitas == "dkm":
        df = pd.read_sql_query("SELECT * FROM ViewLaporanRingkasan", conn)
        filename = "RekapAkhir_DKM.xlsx"
    else:
        df = pd.read_sql_query("SELECT * FROM RekapAkhir", conn)
        filename = "RekapAkhir_JMCare.xlsx"

    conn.close()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RekapAkhir')
    output.seek(0)

    response = make_response(output.read())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

# ------------------------
# ROUTE: Rekap Akhir untuk DKM
# ------------------------
@app.route("/rekapakhir_dkm")
def rekapakhir_dkm():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    conn = get_connection("dkm")  # Ambil koneksi ke DB DKM
    rows = conn.execute("SELECT * FROM ViewLaporanRingkasan").fetchall()
    conn.close()
    return render_template("rekap_akhir_dkm.html", data=rows)

# ------------------------
# ROUTE: Export Rekap Akhir DKM ke Excel
# ------------------------
@app.route("/rekapakhir_dkm/export")
def export_rekapakhir_dkm():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    conn = get_connection("dkm")
    df = pd.read_sql_query("SELECT * FROM ViewLaporanRingkasan", conn)
    conn.close()

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='RekapAkhirDKM')
    output.seek(0)

    response = make_response(output.read())
    response.headers["Content-Disposition"] = "attachment; filename=RekapAkhir_DKM.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

# ------------------------
# ROUTE: Rekap Transaksi (ViewRekapTransaksi)
# ------------------------
@app.route("/rekaptransaksi", methods=["GET", "POST"])
def index_viewrekap():
    if "user" not in session:
        return redirect(url_for("login"))

    # ✅ Tangkap entitas dari dropdown jika dikirim lewat POST
    if request.method == "POST" and "entitas" in request.form:
        session["entitas"] = request.form["entitas"]

    entitas = session.get("entitas", "jurangmangucare")

    # ✅ Tentukan filter JenisAnggota sesuai entitas
    if entitas == "dkm":
        jenis_anggota_1 = "Orang MAS"
    else:
        jenis_anggota_1 = "Orang JMCare"
    
    jenis_anggota_2 = "AkunInternal"

    conn = get_connection(entitas)

    query = """
        SELECT * FROM ViewRekapTransaksi
        WHERE JenisAnggota IN (?, ?)
    """

    anggota_filter = None

    if session["user"] == "admin":
        if request.method == "POST":
            anggota_filter = request.form.get("kode_anggota")
            if anggota_filter:
                query += " AND KodeAnggota = ?"
                rows = conn.execute(query, (jenis_anggota_1, jenis_anggota_2, anggota_filter)).fetchall()
            else:
                rows = conn.execute(query, (jenis_anggota_1, jenis_anggota_2)).fetchall()
        else:
            rows = conn.execute(query, (jenis_anggota_1, jenis_anggota_2)).fetchall()
    else:
        anggota_filter = session["user"]
        query += " AND KodeAnggota = ?"
        rows = conn.execute(query, (jenis_anggota_1, jenis_anggota_2, anggota_filter)).fetchall()

    conn.close()
    return render_template("index.html", data=rows, kode=anggota_filter)


# ------------------------
# ROUTE: Transaksi JMCARE (lihat semua transaksi)
# ------------------------
@app.route("/transaksi_jmcare")
def transaksi_jmcare():
    if "user" not in session or session["user"] == "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    kode_anggota = session["user"]

    conn = get_connection(entitas)
    rows = conn.execute("""
        SELECT Tanggal, KodeAnggota, NamaAnggota, KodeJenisTrans, JenisTransaksi, Jumlah, Uraian
        FROM ViewTransaksiLengkap
        WHERE KodeAnggota = ?
        ORDER BY Tanggal DESC
    """, (kode_anggota,)).fetchall()
    conn.close()

    return render_template("transaksi_user.html", data=rows, judul="Transaksi JurangmanguCare")


# ------------------------
# ROUTE: Transaksi Anggota (lihat semua transaksi)
# ------------------------
@app.route("/transaksi")
def transaksi_user():
    if "user" not in session or session["user"] == "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    kode_anggota = session["user"]

    conn = get_connection(entitas)

    rows = conn.execute("""
        SELECT 
            T.No,
            H.Tanggal,
            T.KodeAnggota,
            A.NamaAnggota,
            T.KodeJenisTrans,
            J.JenisTransaksi,
            T.Uraian,
            T.Jumlah
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        JOIN Anggota A ON T.KodeAnggota = A.KodeAnggota
        JOIN JenisTransaksi J ON T.KodeJenisTrans = J.KodeJenisTrans
        WHERE T.KodeAnggota = ?
        ORDER BY H.Tanggal DESC, T.No DESC
    """, (kode_anggota,)).fetchall()

    conn.close()
    return render_template("transaksi_user.html", data=rows)

# ------------------------
# ROUTE: Pivot Transaksi
# ------------------------
@app.route("/pivot")
def pivot_transaksi():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas") or "jurangmangucare"
    conn = get_connection(entitas)
    rows = conn.execute("SELECT * FROM ViewPivotTransaksi").fetchall()
    conn.close()
    return render_template("pivot_transaksi.html", data=rows)

# ------------------------
# ROUTE: Tambah Transaksi
# ------------------------
@app.route("/tambah", methods=["GET", "POST"])
def tambah():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    # Tangkap entitas yang dipilih di form
    if request.method == "POST" and "entitas" in request.form:
        session["entitas"] = request.form["entitas"]

    entitas = session.get("entitas", "jurangmangucare")
    if entitas == "dkm":
        filter_anggota = "Orang MAS"
    else:
        filter_anggota = "Orang JMCare"

    conn = get_connection(entitas)
    anggota_list = conn.execute("""
        SELECT KodeAnggota, NamaAnggota FROM Anggota
        WHERE JenisAnggota IN (?, 'AkunInternal')
    """, (filter_anggota,)).fetchall()

    jenis_list = conn.execute("""
        SELECT KodeJenisTrans, JenisTransaksi FROM JenisTransaksi
    """).fetchall()

    last_10 = conn.execute("""
        SELECT T.No, T.KodeAnggota, T.KodeJenisTrans, T.Uraian, T.Jumlah, H.Tanggal
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        ORDER BY T.No DESC LIMIT 10
    """).fetchall()

    last_entry = None
    if request.method == "POST":
    # Cek jika form hanya kirim perubahan entitas
        if "tanggal" not in request.form:
            # Jangan proses transaksi, hanya render ulang berdasarkan entitas
            conn.close()
            return render_template("tambah_transaksi.html",
                               anggota_list=anggota_list,
                               jenis_list=jenis_list,
                               last_trans=None,
                               last_10=last_10,
                               today=datetime.today().strftime("%Y-%m-%d"))

        # Proses transaksi seperti biasa
        tanggal_input = request.form.get("tanggal")
        kode_anggota = request.form.get("kode_anggota")
        kode_jenis = request.form.get("kode_jenis")
        uraian = request.form.get("uraian")
        jumlah = request.form.get("jumlah")

        try:
           datetime.strptime(tanggal_input, "%Y-%m-%d")
        except ValueError:
            flash("Format tanggal tidak valid.", "error")
            return redirect(url_for("tambah"))


        result = conn.execute("SELECT IDTanggal FROM HeaderTransaksi WHERE Tanggal = ?", (tanggal_input,)).fetchone()
        if result:
            kd_tanggal = result["IDTanggal"]
        else:
            conn.execute("INSERT INTO HeaderTransaksi (Tanggal) VALUES (?)", (tanggal_input,))
            kd_tanggal = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO Transaksi (KodeAnggota, KodeJenisTrans, Uraian, Jumlah, KdTanggal)
            VALUES (?, ?, ?, ?, ?)
        """, (kode_anggota, kode_jenis, uraian, jumlah, kd_tanggal))
        conn.commit()

        last_entry = conn.execute("""
            SELECT T.*, H.Tanggal FROM Transaksi T
            JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
            WHERE T.rowid = last_insert_rowid()
        """).fetchone()

    conn.close()
    return render_template("tambah_transaksi.html",
                           anggota_list=anggota_list,
                           jenis_list=jenis_list,
                           last_trans=last_entry,
                           last_10=last_10,
                           today=datetime.today().strftime("%Y-%m-%d"))

# ------------------------
# ROUTE: Edit Transaksi
# ------------------------
@app.route("/edit_transaksi/<int:id>", methods=["GET", "POST"])
def edit_transaksi(id):
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    if entitas == "dkm":
        filter_anggota = "Orang MAS"
    else:
        filter_anggota = "Orang JMCare"

    conn = get_connection(entitas)

    if request.method == "POST":
        kode_anggota = request.form.get("kode_anggota")
        kode_jenis = request.form.get("kode_jenis")
        uraian = request.form.get("uraian")
        jumlah = request.form.get("jumlah")

        conn.execute("""
            UPDATE Transaksi
            SET KodeAnggota=?, KodeJenisTrans=?, Uraian=?, Jumlah=?
            WHERE No=?
        """, (kode_anggota, kode_jenis, uraian, jumlah, id))
        conn.commit()
        conn.close()
        return redirect(url_for("tambah"))

# Ambil data transaksi
    data = conn.execute("SELECT * FROM Transaksi WHERE No = ?", (id,)).fetchone()

# Pastikan mengambil KodeAnggota dan NamaAnggota, bukan hanya KodeAnggota

    anggota_list = conn.execute("""
        SELECT KodeAnggota, NamaAnggota FROM Anggota
        WHERE JenisAnggota = ?
    """, (filter_anggota,)).fetchall()


    jenis_list = conn.execute("""
        SELECT KodeJenisTrans, JenisTransaksi FROM JenisTransaksi
      """).fetchall()

    conn.close()

    return render_template("edit_transaksi.html", data=data, anggota_list=anggota_list, jenis_list=jenis_list)

# ------------------------
# ROUTE: Hapus Transaksi
# ------------------------
@app.route("/hapus_transaksi/<int:id>", methods=["GET", "POST"])
def hapus_transaksi(id):
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas") or "jurangmangucare"
    conn = get_connection(entitas)

    transaksi = conn.execute("""
        SELECT T.No, T.KodeAnggota, T.KodeJenisTrans, T.Uraian, T.Jumlah, H.Tanggal
        FROM Transaksi T
        JOIN HeaderTransaksi H ON T.KdTanggal = H.IDTanggal
        WHERE T.No = ?
    """, (id,)).fetchone()

    if request.method == "POST":
        # Pastikan Anda sudah punya tabel LogHapusTransaksi jika ingin logging
        try:
            conn.execute("""
                INSERT INTO LogHapusTransaksi (NoTransaksi, KodeAnggota, KodeJenisTrans, Uraian, Jumlah, Tanggal, DihapusOleh, WaktuPenghapusan)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaksi["No"],
                transaksi["KodeAnggota"],
                transaksi["KodeJenisTrans"],
                transaksi["Uraian"],
                transaksi["Jumlah"],
                transaksi["Tanggal"],
                session.get("user"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
        except:
            pass  # Abaikan kalau LogHapusTransaksi belum ada

        conn.execute("DELETE FROM Transaksi WHERE No = ?", (id,))
        conn.commit()
        conn.close()
        return redirect(url_for("tambah"))

    conn.close()
    return render_template("konfirmasi_hapus.html", transaksi=transaksi)

# ------------------------
# ROUTE: Tambah Anggota
# ------------------------
@app.route("/tambah_anggota", methods=["GET", "POST"])
def tambah_anggota():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    message = None

    if request.method == "POST":
        kode = request.form["kode_anggota"].strip().upper()
        nama = request.form["nama_anggota"].strip()
        jenis = request.form["jenis_anggota"].strip()

        # Cek apakah kode sudah ada
        exists = conn.execute("SELECT 1 FROM Anggota WHERE KodeAnggota = ?", (kode,)).fetchone()
        if exists:
            message = f"⚠️ Kode anggota '{kode}' sudah ada. Gunakan kode lain."
        else:
            conn.execute("INSERT INTO Anggota (KodeAnggota, NamaAnggota, JenisAnggota) VALUES (?, ?, ?)",
                         (kode, nama, jenis))
            conn.commit()
            message = f"✅ Anggota '{nama}' berhasil ditambahkan."

    conn.close()
    return render_template("tambah_anggota.html", message=message)
    
# ------------------------
# ROUTE: Tambah Jenis Transaksi
# ------------------------
@app.route("/tambah_jenis", methods=["GET", "POST"])
def tambah_jenis():
    if "user" not in session or session["user"] != "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    message = None

    if request.method == "POST":
        kode = request.form["kode"]
        nama = request.form["nama"]

        conn = get_connection(entitas)
        existing = conn.execute("SELECT 1 FROM JenisTransaksi WHERE KodeJenisTrans = ?", (kode,)).fetchone()

        if existing:
            message = f"Kode Jenis Transaksi '{kode}' sudah ada. Gunakan kode lain."
        else:
            conn.execute("INSERT INTO JenisTransaksi (KodeJenisTrans, JenisTransaksi) VALUES (?, ?)", (kode, nama))
            conn.commit()
            message = f"Jenis Transaksi '{nama}' berhasil ditambahkan."
        conn.close()

    return render_template("tambah_jenis.html", message=message)


# ------------------------
# ROUTE: Rekap Anggota
# ------------------------

@app.route("/rekapanggota", methods=["GET", "POST"])
def rekapanggota():
    if "user" not in session or session["user"] == "admin":
        return redirect(url_for("login"))

    entitas = session.get("entitas", "jurangmangucare")
    conn = get_connection(entitas)

    # Pilih view dan file template berdasarkan entitas
    if entitas == "dkm":
        rows = conn.execute("SELECT * FROM ViewLaporanRingkasan").fetchall()
        template_name = "rekap_anggota_dkm.html"
    else:
        rows = conn.execute("SELECT * FROM RekapAkhir").fetchall()
        template_name = "rekap_anggota_jmcare.html"

    conn.close()
    return render_template(template_name, data=rows)



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

