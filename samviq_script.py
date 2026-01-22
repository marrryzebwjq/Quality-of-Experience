#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Expérience SAMVIQ pour PsychoPy
6 références (3 sources x 2 caméras) × 6 conditions (original + 5 algorithmes de distorsion)
"""

from psychopy import visual, core, event, data, gui
from psychopy.hardware import keyboard
import random
import os
import pandas as pd
import numpy as np
import cv2

# Forcer le backend vidéo à opencv (meilleur pour les fichiers AVI)
from psychopy import prefs
prefs.hardware['audioLib'] = ['ptb', 'sounddevice', 'pyo', 'pygame']
prefs.hardware['videoLib'] = ['opencv', 'moviepy', 'ffpyplayer']

# ===== CONFIGURATION =====
ORIGINALS = ['Left']
REFERENCES = ['Center_Book_arrival', 'Right_Book_arrival',
              'Center_Lovebird',     'Right_Lovebird',
              'Center_Newspaper',    'Right_Newspaper']
CONDITIONS = ['Original', 'Fehn_c', 'Fehn_i', 'Holes', 'ICIP_TMM', 'ICME']
VIDEO_FOLDER = r'IRCCyN_IVC_DIBR_Videos\Videos'
CSV_PATH = r'results'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== BOÎTE DE DIALOGUE =====
exp_info = {'participant': '', 'session': '01'}
dlg = gui.DlgFromDict(dictionary=exp_info, title='SAMVIQ')
if not dlg.OK:
    core.quit()

# ===== CRÉATION DE LA FENÊTRE =====
win = visual.Window(
    size=[1920, 1080],
    fullscr=True,
    units='height',
    color=[0, 0, 0]
)

kb = keyboard.Keyboard()

# ===== TEXTES D'INSTRUCTIONS =====
instructions = visual.TextStim(
    win,
    text="""Bienvenue dans cette expérience d'évaluation de qualité vidéo.

Vous allez évaluer différentes versions de plusieurs vidéos.
Pour chaque référence, vous verrez 6 versions à comparer.

INSTRUCTIONS:
- Cliquez sur les boutons pour voir/revoir chaque vidéo
- Utilisez les curseurs pour noter la qualité (0 = mauvaise, 100 = excellente)
- Vous pouvez revoir les vidéos autant de fois que nécessaire
- Une fois satisfait de vos notations, cliquez sur "Suivant"

Appuyez sur ESPACE pour commencer""",
    height=0.03,
    wrapWidth=0.9
)

# ===== GÉNÉRATION DES TRIALS =====
trials_list = []

# originales TODO

for ref in REFERENCES:
    # Créer une liste des conditions pour cette référence
    cond_list = CONDITIONS.copy()
    random.shuffle(cond_list)  # Randomiser l'ordre de présentation
    
    # Assigner des labels anonymes (A, B, C, D, E, F)
    labels = ['A', 'B', 'C', 'D', 'E', 'F']
    random.shuffle(labels)
    
    trial = {
        'reference': ref,
        'conditions': cond_list,
        'labels': labels
    }
    trials_list.append(trial)

random.shuffle(trials_list)  # Randomiser l'ordre des références

# ===== FICHIER DE DONNÉES =====
filename = f"data/{exp_info['participant']}_{exp_info['session']}_samviq"
os.makedirs('data', exist_ok=True)

# ===== AFFICHER INSTRUCTIONS =====
instructions.draw()
win.flip()
event.waitKeys(keyList=['space'])

# ===== VARIABLES POUR L'INTERFACE =====
mouse = event.Mouse(win=win)

def create_rating_interface(labels):
    """Crée les éléments de l'interface de notation"""
    buttons = []
    sliders = []
    button_labels = []
    
    y_start = 0.35
    button_width = 0.12
    button_height = 0.06
    spacing = 0.15
    
    for i, label in enumerate(labels):
        x_pos = -0.4 + i * spacing
        
        # Bouton vidéo
        button = visual.Rect(
            win,
            width=button_width,
            height=button_height,
            pos=[x_pos, y_start],
            fillColor='darkblue',
            lineColor='white'
        )
        buttons.append(button)
        
        # Label du bouton
        btn_label = visual.TextStim(
            win,
            text=label,
            pos=[x_pos, y_start],
            height=0.03,
            color='white'
        )
        button_labels.append(btn_label)
        
        # Slider de notation
        slider = visual.Slider(
            win,
            pos=[x_pos, -0.05],
            size=[0.03, 0.4],
            ticks=[0, 25, 50, 75, 100],
            granularity=1,
            style='slider',
            flip=True,
            labelHeight=0.02,
            markerColor='red'
        )
        sliders.append(slider)
    
    return buttons, sliders, button_labels

def find_video(originals, ref, condition, data):
    to_cam_position, video_label = ref.split('_', 1)
    if condition == 'Original':
        filtre = (
            (data['Algo'] == condition) &
            (data['from_cam_position'] == originals) &
            (data['Video'].str.contains(video_label, case=False, na=False))
        )
    else :
        filtre = (
            (data['Algo'] == condition) &
            (data['from_cam_position'] == originals) &
            (data['to_cam_position'] == to_cam_position) &
            (data['Video'].str.contains(video_label, case=False, na=False))
        )
    candidates = data.loc[filtre, 'Video_path']
    if candidates.empty:
        print(f"No video found for {originals}, {ref}, {condition}")
    return candidates.iloc[0] if not candidates.empty else None

def resolve_video_path(video_path):
    """Resolve a potentially relative/CSV-provided path to an existing file.
    Tries several candidates under the project and VIDEO_FOLDER.
    """
    if not video_path:
        return None
    p = os.path.normpath(str(video_path))
    candidates = []

    # As-is (absolute or relative from CWD)
    candidates.append(p)

    # Relative to project base
    candidates.append(os.path.normpath(os.path.join(BASE_DIR, p)))

    # Under configured VIDEO_FOLDER (accept filename or subpath)
    video_dir_abs = os.path.normpath(os.path.join(BASE_DIR, VIDEO_FOLDER))
    candidates.append(os.path.normpath(os.path.join(video_dir_abs, p)))
    candidates.append(os.path.normpath(os.path.join(video_dir_abs, os.path.basename(p))))

    for c in candidates:
        if os.path.exists(c):
            return c
    # Not found
    print(f"[SAMVIQ] Video file not found. Tried: {candidates}")
    return None

def show_video(video_path):
    """Affiche une vidéo en utilisant OpenCV directement"""
    resolved = resolve_video_path(video_path)
    if not resolved:
        # Fichier introuvable: afficher un message explicite
        msg = visual.TextStim(
            win,
            text=f"Fichier vidéo introuvable:\n{video_path}\n\nVérifiez le chemin et le dossier 'IRCCyN_IVC_DIBR_Videos/\nVideos'.\n(Appuyez sur ESPACE)",
            height=0.04
        )
        msg.draw()
        win.flip()
        event.waitKeys(keyList=['space'])
        return
    
    print(f"[DEBUG] Lecture de: {resolved}")
    
    try:
        # Ouvrir la vidéo avec OpenCV directement
        cap = cv2.VideoCapture(resolved)
        
        if not cap.isOpened():
            raise Exception("Impossible d'ouvrir la vidéo avec OpenCV")
        
        # Obtenir les propriétés
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25  # Valeur par défaut
        frame_delay = 1.0 / fps
        
        print(f"[DEBUG] FPS: {fps}, frame_delay: {frame_delay}s")
        
        # Créer un stimulus image pour afficher les frames
        img_stim = visual.ImageStim(
            win,
            size=(1.6, 0.9),
            pos=(0, 0)
        )
        
        frame_count = 0
        clock = core.Clock()
        next_t = 0.0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print(f"[DEBUG] Fin de la vidéo après {frame_count} frames")
                break
            
            # Convertir BGR (OpenCV) en RGB (PsychoPy)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Inverser verticalement (OpenCV lit à l'envers pour PsychoPy)
            frame_rgb = cv2.flip(frame_rgb, 0)
            
            # Normaliser à [0, 1] pour PsychoPy
            frame_norm = frame_rgb.astype(float) / 255.0
            
            # Mettre à jour le stimulus
            img_stim.image = frame_norm
            
            # Afficher
            win.clearBuffer()
            img_stim.draw()
            win.flip()
            
            frame_count += 1
            
            # Debug première frame
            if frame_count == 1:
                print(f"[DEBUG] Première frame affichée - shape: {frame_rgb.shape}")
            
            # Vérifier les touches
            keys = event.getKeys()
            if 'escape' in keys or 'space' in keys:
                print(f"[DEBUG] Vidéo arrêtée par l'utilisateur après {frame_count} frames")
                break
            
            # Cadencer à fps nominal sans ralentir (wait seulement si en avance)
            next_t += frame_delay
            wait_time = next_t - clock.getTime()
            if wait_time > 0:
                core.wait(wait_time)
            else:
                # Si on est en retard, recaler pour éviter d'accumuler
                next_t = clock.getTime()
        
        cap.release()
        print(f"[DEBUG] Vidéo terminée ({frame_count} frames)")
        
    except Exception as e:
        print(f"[ERREUR] Lecture de {resolved}: {e}")
        import traceback
        traceback.print_exc()
        
        # Afficher un message d'erreur à l'utilisateur
        error_msg = visual.TextStim(
            win,
            text=f"Erreur de lecture vidéo:\n{str(e)}\n\n(Appuyez sur ESPACE)",
            height=0.03,
            color='red'
        )
        error_msg.draw()
        win.flip()
        event.waitKeys(keyList=['space'])

# ===== BOUCLE PRINCIPALE =====
all_results = []
df_videos = pd.read_csv(CSV_PATH + "/df_videos_processed.csv")

for trial_num, trial in enumerate(trials_list, 1):
    ref = trial['reference']
    conditions = trial['conditions']
    labels = trial['labels']
    
    # Créer l'interface
    buttons, sliders, button_labels = create_rating_interface(labels)
    
    # Instructions pour ce trial
    trial_text = visual.TextStim(
        win,
        text=f"Référence {trial_num}/{len(trials_list)}: {ref}\n\nCliquez sur les boutons pour voir les vidéos",
        pos=[0, 0.45],
        height=0.03
    )
    
    next_button = visual.Rect(
        win,
        width=0.2,
        height=0.08,
        pos=[0, -0.45],
        fillColor='darkgreen',
        lineColor='white'
    )
    next_label = visual.TextStim(
        win,
        text='Suivant',
        pos=[0, -0.45],
        height=0.03
    )
                                                                #### TODO
    # Mapping label -> condition
    label_to_condition = {labels[i]: conditions[i] for i in range(len(labels))}
    
    # Boucle d'évaluation pour cette référence
    continue_trial = True
    while continue_trial:
        # Dessiner l'interface
        trial_text.draw()
        
        for i in range(len(labels)):
            buttons[i].draw()
            button_labels[i].draw()
            sliders[i].draw()
        
        next_button.draw()
        next_label.draw()
        
        win.flip()
        
        # Vérifier les clics
        if mouse.getPressed()[0]:
            pos = mouse.getPos()
            
            # Vérifier les boutons vidéo
            for i, button in enumerate(buttons):
                if button.contains(pos):
                    condition = label_to_condition[labels[i]]
                    #video_file = f"{VIDEO_FOLDER}{ref}_{condition}.mp4"
                    video_file = find_video(ORIGINALS[0], ref, condition, df_videos)
                    show_video(video_file)
                    core.wait(0.3)  # Anti-rebond
            
            # Vérifier le bouton suivant
            if next_button.contains(pos):
                # Vérifier que toutes les notes sont données
                all_rated = all(slider.rating is not None for slider in sliders)
                if all_rated:
                    continue_trial = False
                    core.wait(0.3)
                else:
                    warning = visual.TextStim(
                        win,
                        text="Veuillez noter toutes les vidéos avant de continuer",
                        pos=[0, -0.35],
                        height=0.025,
                        color='red'
                    )
                    warning.draw()
                    win.flip()
                    core.wait(1.5)
        
        # Vérifier la touche échap
        if 'escape' in event.getKeys():
            win.close()
            core.quit()
    
    # Enregistrer les résultats
    for i, label in enumerate(labels):
        result = {
            'participant': exp_info['participant'],
            'session': exp_info['session'],
            'trial': trial_num,
            'reference': ref,
            'label': label,
            'condition': label_to_condition[label],
            'rating': sliders[i].rating
        }
        all_results.append(result)

# ===== SAUVEGARDER LES DONNÉES =====
df = pd.DataFrame(all_results)
df.to_csv(f"{filename}.csv", index=False)

# ===== MESSAGE DE FIN =====
end_text = visual.TextStim(
    win,
    text="Merci de votre participation!\n\nAppuyez sur ESPACE pour quitter",
    height=0.04
)
end_text.draw()
win.flip()
event.waitKeys(keyList=['space'])

win.close()
core.quit()