import slmpy
import matplotlib.pyplot as plt

# As of now a thin wrapper on the slmpy library

class SLM:
    def __init__(self, config, bDummy=0):
        # config is a SLMConfig
        self.monitor = config.monitor
        if not bDummy:
            if self.monitor = None:
                self.slm = slmpy.SLMdisplay(isImageLock = True)
            else:
                self.slm = slmpy.SLMdisplay(monitor = self.monitor, isImageLock = True)

    def __del__(self):
        if not bDummy:
            self.slm.close()

    def stop(self):
        if not bDummy:
            self.slm.close()

    def send(self, img):
        if bDummy:
            plt.imshow(img)
            plt.colorbar()
            plt.show()
        else:
            self.slm.updateArray(img)
