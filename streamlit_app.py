import streamlit as st

st.title("🎈 LA NUEVA APLICACION")
st.write(
    "pagina inicial [docs.streamlit.io](https://docs.streamlit.io/)."
)
st.image("/workspaces/blank-app-1/LOGOCC.png",caption="CONTACTENOS")

left, middle, right = st.columns(3)



if left.button("BOTON PLANO", use_container_width=False):
 
    left.markdown("HIZO CLICK EN EL BOTON PLANO.")
if middle.button("Emoji button", icon="😃", use_container_width=True):
    middle.markdown("USTED HIZO CLICK EN EL BOTON DE EMOJI.")
if right.button("MATERIALES", icon=":material/mood:", use_container_width=True):
    right.markdown("CUALES MATERIALES.")
