#!/usr/bin/ruby

# delete_older_than.rb
#
# Copyright 2007-2011 Rohit Mehta <rohit (at) engr.uconn.edu>
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
def delete_older(path, age_in_seconds)

  Dir.foreach(path) { |name|

    next if name == '.' or name == '..'
 
    full_name = File.join(path, name)

    case File.ftype(full_name)

    when "file"
      age = Time.now - File.mtime(full_name)

      if age > age_in_seconds
        puts "Deleting file #{full_name}"
        File.unlink(full_name)
      end

    when "directory"
      delete_older(full_name, age_in_seconds)
    #  if (Dir.entries(full_name) - ['.', '..']).empty?
    #    puts "Deleting directory #{full_name}"
    #    Dir.rmdir(full_name)
    #  end
    end

  }
end

path = ARGV.shift or raise "Missing path to delete"
age  = ARGV.shift or raise "Missing age in days"

age_in_seconds = age.to_i * 24*60*60


delete_older(path, age_in_seconds) rescue puts "Error: #$!"
