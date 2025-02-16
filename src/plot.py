from io import BytesIO
import base64

def encode_plot(fig):
    img = BytesIO()

    fig.savefig(img, format='png', dpi = 300)
    #fig.close()
    img.seek(0)
    return(base64.b64encode(img.getvalue()).decode('utf8'))
