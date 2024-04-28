from bokeh_histogram import visualize_histogram
import mysql.connector as mysq



def get_guasti(connection,guasti,risolti):
    
    cur = connection.cursor()
    query = "SELECT COUNT(report.classe) FROM report WHERE report.classe=%s AND report.stato=%s"

    cur.execute(query,(guasti,risolti))
    count = cur.fetchall()  # Fetch the count value
    connection.commit()
    #cur.close()
    #connection.close()  # Close the connection
    return count
def estrai(lista):
    lista2 = []
    for i in  range (0,len(lista)):
        lista2.append(lista[i][0])
    return  lista2
'''
connection = mysq.connect(
    host="localhost",
    user="root",
    password="",
    database="gestione_guasti",
    port=3306 
)
'''
def home(connection):
    cur = connection.cursor()
    cur.execute("select distinct(classe) from report")
    aule_t = cur.fetchall()
    aule = estrai(aule_t)
    y_data1 = []
    y_data2 = []
    stato1=True
    stato2=False
    for i in range (len(aule)):
        y_data1.append(get_guasti(connection,aule[i],stato1))
        y_data2.append(get_guasti(connection,aule[i],stato2))
    print(y_data1)
    print(y_data2)
    print("aule", aule)

    visualize_histogram(aule, y_data1, y_data2)
'''
if __name__ == "__main__":
    home(connection)
'''