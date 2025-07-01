import streamlit as st

st.title("🎈 LA NUEVA APLICACION")
st.write(
    "pagina inicial [docs.streamlit.io](https://docs.streamlit.io/)."
)
st.image("/workspaces/blank-app-1/LOGOCC.png",caption="CONTACTENOS")
age = st.slider("que valor le calcula hasta 130?", 0, 130, 25)

title = st.text_input("ingrese texto", "escriba aqui")
st.write("Lo que escribio es.....", title)

number1 = st.number_input("Insert a numero")
st.write("The current number is ", number1)


left, middle, right = st.columns(3)



if left.button("BOTON PLANO", use_container_width=False):
 
    left.markdown("HIZO CLICK EN EL BOTON PLANO.")
if middle.button("Emoji button", icon="😃", use_container_width=True):
    middle.markdown("USTED HIZO CLICK EN EL BOTON DE EMOJI.")
if right.button("MATERIALES", icon=":material/mood:", use_container_width=True):
    right.markdown("CUALES SON LOS MATERIALES.")
