from bokeh.plotting import figure, output_file, save
from bokeh.io import curdoc
import os

def visualize_histogram(parole, conteggi1, conteggi2):
    # Creazione del grafico
    p = figure(x_range=parole, width=700, height=550, title="guasti/aule")

    # Impostazione delle etichette
    p.xgrid.grid_line_color = None
    p.y_range.start = 0
    p.xaxis.major_label_orientation = 1.2

    total_conteggi1 = [sum(tupla[0]) for tupla in conteggi1]
    total_conteggi2 = [sum(tupla[0]) for tupla in conteggi2]
    total_conteggi = [c1 + c2 for c1, c2 in zip(total_conteggi1, total_conteggi2)]

    p.vbar(x=parole, top=total_conteggi, width=0.8, color='green', legend_label='aggiustato')
    p.vbar(x=parole, top=conteggi2, width=0.8, color='red', legend_label='NON aggiustato')

    p.legend.location = "top_right"
    p.legend.click_policy = "hide"

    # Salvataggio del grafico su un file HTML
    output_file("pagine/istogramma_guasti.html", title="istogramma")
    filena = "pagine/istogramma_guasti.html"

    # Applica un tema scuro predefinito
    curdoc().theme = "dark_minimal"
    save(p, filename=filena)

    # Percorso del file HTML generato da Bokeh
    html_file_path = "pagine/istogramma_guasti.html"

    # Aggiungi il tag <link> per l'icona al file HTML
    icon_link = '<link rel="icon" type="image/x-icon" href="/icone/favicon.ico" />'

    # CSS per lo sfondo scuro
    css_code = """
        <style>
            body {
                background-color: #1e1e1e;  /* Colore di sfondo scuro */
            }
        </style>
    """

    # Apri il file HTML e inserisci il CSS
    with open(html_file_path, 'r+') as f:
        content = f.read()
        # Cerca il tag <head> all'interno del file HTML
        head_index = content.find('<head>')
        if head_index != -1:
            # Inserisci il CSS all'interno del tag <head>
            updated_content = content[:head_index + 6] + css_code + content[head_index + 6:]
            # Inserisci il tag per l'icona subito dopo il tag <head>
            updated_content = updated_content.replace('<head>', f'<head>\n{icon_link}', 1)
            # Sovrascrivi il file HTML con il contenuto aggiornato
            f.seek(0)
            f.write(updated_content)
            f.truncate()


