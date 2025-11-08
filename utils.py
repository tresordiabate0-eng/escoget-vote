import io, os, csv, qrcode
from datetime import datetime
from flask import send_file
from werkzeug.utils import secure_filename

def save_upload(file_storage, upload_folder):
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename)
    name, ext = os.path.splitext(filename)
    filename = f"{name}_{int(datetime.utcnow().timestamp())}{ext}"
    path = os.path.join(upload_folder, filename)
    file_storage.save(path)
    return filename

def generate_qr_bytes(url):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def export_votes_csv(votes):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Candidat", "Votant", "Infos votant", "Date du vote"])
    for v in votes:
        writer.writerow([
            f"{v.candidate.first_name} {v.candidate.last_name}",
            v.voter_name,
            v.voter_meta or "",
            v.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="votes_export.csv"
    )
