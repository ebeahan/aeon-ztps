# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!

Vagrant.configure(2) do |config|
  config.vm.box = "robwc/minitrusty64"
  config.vm.hostname = 'aeon-ztp'

  config.vm.synced_folder ".", "/aeon-ztp", type: "nfs"

  config.vm.network "forwarded_port", guest: 8888, host: 8888
  config.vm.network "private_network", type: "dhcp"

  config.vm.provision "shell", inline: <<-EOS
#    sudo mkdir -p /media/sf_Projects/tmp
#    sudo chmod a+rwx /media/sf_Projects/tmp
#    ln -s /vagrant /media/sf_Projects/Leblon
#
    /aeon-ztp/vagrant_vm_setup.sh
  EOS

  config.vm.provider "virtualbox" do |vb|
    vb.name = 'aeon-ztp'
    vb.gui = true
    vb.memory = '1024'
  end
end
